"""Paired offline evaluation on the v2 development corpus.

Engines compared on identical cases and identical uploaded documents:
  baseline      - existing heuristic verifier (AIVerifierService local fallback + lexical RAG)
  candidate_v1  - frozen development candidate v1 (app/services/development_verifier.py) on
                  its original input path: top-5 lexically retrieved chunks
  candidate_v2  - development candidate v2 (app/services/development_verifier_v2) on full
                  extracted documents, plus component ablations and perturbation robustness

Gemini generation, embeddings and OCR are disabled; a guard fails the run if
any Gemini request is attempted.  Results are synthetic development metrics,
not real-world accuracy.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.services import gemini_api, rag
from app.services.ai_verifier import ai_verifier
from app.services.development_verifier import verify_development_case
from app.services.development_verifier_v2 import (
    CaseInput, Decision, ENGINE_VERSION, VerifierConfig, load_documents, verify_case,
)
from app.services.development_verifier_v2.audit import redact_finding
from app.services.fraud_detector import format_inr
from evaluate_fundraising import evaluate as evaluate_baseline
from perturbations import PERTURBATIONS, perturb_case

DATASET = Path(__file__).with_name("development_scenarios_v2.jsonl")
FREEZE_MANIFEST = Path(__file__).with_name("development_candidate_v2_freeze.json")
V2_PACKAGE = ROOT / "app/services/development_verifier_v2"
DECISIONS = ["APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR"]
LEGACY = {"AUTO_APPROVE": "APPROVED", "NEEDS_MORE_INFO": "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW": "FLAG_FOR_REVIEW",
          "REJECT": "REJECTED", "SYSTEM_ERROR": "VERIFICATION_ERROR"}
FLAG_DECISIONS = {"FLAG_FOR_REVIEW", "REJECTED"}
ABLATIONS = {
    "full": VerifierConfig(),
    "without_cross_document": VerifierConfig(enable_cross_document=False),
    "without_category": VerifierConfig(enable_category=False),
    "without_semantic": VerifierConfig(enable_semantic=False),
    "requirements_only": VerifierConfig(enable_cross_document=False, enable_semantic=False),
}
PLANTED_TO_FINDING = {"identity": {"identity"}, "settlement": {"settlement", "amount"}, "amount": {"amount"},
                      "chronology": {"chronology"}, "identifier": {"identifier"}, "institution": {"institution"},
                      "payment_routing": {"payment_routing"}, "service": {"service"}, "eligibility": {"eligibility"}}


# ------------------------------------------------------------------ helpers
def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_digest() -> dict:
    files = {p.name: digest(p) for p in sorted(V2_PACKAGE.glob("*.py"))}
    combined = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"files": files, "combined": combined}


def wilson(successes: int, total: int, z: float = 1.96):
    if not total:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def ratio(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def metrics(rows):
    """Fraud is positive; legitimate and borderline are negative.

    `flagged` = FLAG_FOR_REVIEW or REJECTED (plus, for the two legacy engines, any
    emitted red flag, which is how the production submission path marks a
    campaign FLAGGED).  NEEDS_MORE_INFORMATION is *not* a fraud detection.
    """
    fraud = [r for r in rows if r["ground_truth"] == "fraudulent"]
    legit = [r for r in rows if r["ground_truth"] == "legitimate"]
    negatives = [r for r in rows if r["ground_truth"] != "fraudulent"]
    tp = sum(r["flagged"] for r in fraud)
    fp = sum(r["flagged"] for r in negatives)
    fn, tn = len(fraud) - tp, len(negatives) - fp
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / len(fraud) if fraud else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
    count = Counter(r["decision"] for r in rows)
    n = len(rows)
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    nmi_fraud = sum(r["decision"] == "NEEDS_MORE_INFORMATION" for r in fraud)
    nmi_negative = sum(r["decision"] == "NEEDS_MORE_INFORMATION" for r in negatives)
    return {
        "cases": n,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "precision": round(precision, 4) if precision is not None else None,
        "precision_ci95": wilson(tp, tp + fp),
        "recall": round(recall, 4) if recall is not None else None, "recall_ci95": wilson(tp, len(fraud)),
        "f1": round(f1, 4),
        "false_positive_rate": ratio(fp, len(negatives)), "false_positive_rate_ci95": wilson(fp, len(negatives)),
        "legitimate_false_positive_rate": ratio(sum(r["flagged"] for r in legit), len(legit)),
        "fraudulent_auto_approval_rate": ratio(sum(r["decision"] == "APPROVED" for r in fraud), len(fraud)),
        "legitimate_auto_approval_rate": ratio(sum(r["decision"] == "APPROVED" for r in legit), len(legit)),
        "manual_review_rate": ratio(count["FLAG_FOR_REVIEW"], n),
        "needs_more_information_rate": ratio(count["NEEDS_MORE_INFORMATION"], n),
        "rejection_rate": ratio(count["REJECTED"], n),
        "runtime_error_rate": ratio(count["VERIFICATION_ERROR"], n),
        "human_follow_up_rate": ratio(n - count["APPROVED"], n),
        "decision_counts": {d: count[d] for d in DECISIONS},
        "decision_matrix": {label: {d: sum(r["decision"] == d for r in rows if r["ground_truth"] == label)
                                    for d in DECISIONS} for label in ("legitimate", "fraudulent", "borderline")},
        "secondary_convention_nmi_counts_as_detection": {
            "note": "Reported for transparency only. Not the primary metric: an information request is not a fraud finding.",
            "recall": ratio(tp + nmi_fraud, len(fraud)),
            "false_positive_rate": ratio(fp + nmi_negative, len(negatives)),
        },
        "latency_ms": ({"mean": round(statistics.mean(latencies), 3), "median": round(statistics.median(latencies), 3),
                        "p95": round(sorted(latencies)[max(0, math.ceil(.95 * len(latencies)) - 1)], 3)}
                       if latencies else None),
    }


def grouped(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {name: metrics(group) for name, group in sorted(groups.items())}


def load_cases(split: str):
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = Counter(c["ground_truth"] for c in cases)
    if len(cases) != 120 or labels != {"legitimate": 45, "fraudulent": 45, "borderline": 30}:
        raise ValueError(f"Unexpected corpus: {len(cases)} cases, {dict(labels)}")
    family_splits = defaultdict(set)
    for c in cases:
        family_splits[c["scenario_family"]].add(c["split"])
    if any(len(s) != 1 for s in family_splits.values()):
        raise ValueError("A scenario family crosses the tune/validation split")
    return [c for c in cases if split == "all" or c["split"] == split]


def materialize(cases, directory: Path):
    references = {}
    for case in cases:
        refs = []
        for index, document in enumerate(case["input"].get("documents", []), start=1):
            name = f"{case['case_id'].lower()}-{index}.txt"
            (directory / name).write_text(document["content"], encoding="utf-8")
            refs.append({"doc_type": document["doc_type"], "title": document["title"],
                         "file_url": f"/private-documents/{name}"})
        references[case["case_id"]] = refs
    return references


def case_input(data, documents):
    submitted = data.get("submitted_on")
    return CaseInput(title=data["title"], category=data["category"], story=data["story"],
                     goal_amount=data["goal_amount"], beneficiary_name=data.get("beneficiary_name"),
                     beneficiary_type=data.get("beneficiary_type"), city=data.get("city"), state=data.get("state"),
                     submitted_on=date.fromisoformat(submitted) if submitted else None, documents=documents)


def base_row(case):
    return {"case_id": case["case_id"], "ground_truth": case["ground_truth"], "category": case["input"]["category"],
            "split": case["split"], "scenario_family": case["scenario_family"],
            "document_source": case["document_source"], "variant": case["variant"],
            "expected_action": case["expected_action"], "document_count": len(case["input"].get("documents", []))}


# ------------------------------------------------------------------ engines
async def run_baseline(cases):
    raw = await evaluate_baseline([dict(c, scenario_group=c["scenario_family"]) for c in cases])
    by_id = {c["case_id"]: c for c in cases}
    rows = []
    for row in raw:
        decision = LEGACY[row["recommendation"]]
        rows.append({**base_row(by_id[row["case_id"]]), "decision": decision,
                     "flagged": decision in FLAG_DECISIONS or row["red_flag_count"] > 0,
                     "latency_ms": row["latency_ms"], "red_flag_count": row["red_flag_count"]})
    return rows


async def run_v1(cases, references, directory):
    rows = []
    for case in cases:
        data = case["input"]
        started = time.perf_counter()
        query = " ".join([data["title"], data["category"], data.get("beneficiary_name") or "",
                          f"{data.get('city', '')}, {data.get('state', '')}".strip(", "), data["story"],
                          format_inr(data["goal_amount"])])
        retrieved = await rag.retrieve_evidence(references[case["case_id"]], query, top_k=5)
        try:
            output = verify_development_case(data["title"], data["category"], data["story"], data["goal_amount"],
                                             beneficiary_name=data.get("beneficiary_name"),
                                             documents=[chunk["text"] for chunk in retrieved])
            decision, red_flags, error = LEGACY[output.result.recommendation], output.result.red_flags, None
        except Exception as exc:     # the frozen v1 is evaluated as-is
            decision, red_flags, error = "VERIFICATION_ERROR", [], type(exc).__name__
        rows.append({**base_row(case), "decision": decision,
                     "flagged": decision in FLAG_DECISIONS or bool(red_flags),
                     "latency_ms": (time.perf_counter() - started) * 1000, "error_type": error,
                     "retrieved_chunks": len(retrieved)})
    return rows


def run_v2(cases, references, directory, config, keep_detail=False):
    rows, details = [], {}
    for case in cases:
        started = time.perf_counter()
        documents = load_documents(references[case["case_id"]], directory)
        result = verify_case(case_input(case["input"], documents), config)
        elapsed = (time.perf_counter() - started) * 1000
        decision = result.decision.value
        material_kinds = sorted({f.kind for f in result.findings if f.severity.value == "material"
                                 and f.confidence >= config.flag_confidence})
        rows.append({**base_row(case), "decision": decision, "flagged": decision in FLAG_DECISIONS,
                     "latency_ms": elapsed, "authenticity_score": result.authenticity_score,
                     "finding_codes": sorted({f.code for f in result.findings}), "material_kinds": material_kinds,
                     "all_finding_kinds": sorted({f.kind for f in result.findings}),
                     "unmet_requirements": [r.key for r in result.requirements if not r.satisfied],
                     "influencing_dimensions": result.influencing_dimensions})
        if keep_detail:
            details[case["case_id"]] = result
    return rows, details


# ---------------------------------------------------------------- analyses
def consistency_report(cases, rows):
    """Did the engine find the specific contradiction that was planted?"""
    by_id = {r["case_id"]: r for r in rows}
    per_kind = defaultdict(lambda: {"planted": 0, "detected_as_material": 0, "detected_any_severity": 0})
    for case in cases:
        for kind in case["planted_inconsistencies"]:
            row = by_id[case["case_id"]]
            expected = PLANTED_TO_FINDING[kind]
            per_kind[kind]["planted"] += 1
            per_kind[kind]["detected_as_material"] += bool(expected & set(row["material_kinds"]))
            per_kind[kind]["detected_any_severity"] += bool(expected & set(row["all_finding_kinds"]))
    planted_total = sum(v["planted"] for v in per_kind.values())
    clean = [by_id[c["case_id"]] for c in cases if c["ground_truth"] == "legitimate"]
    borderline = [by_id[c["case_id"]] for c in cases if c["ground_truth"] == "borderline"]
    unplanted_fraud = [by_id[c["case_id"]] for c in cases
                       if c["ground_truth"] == "fraudulent" and not c["planted_inconsistencies"]]
    return {
        "by_planted_kind": {k: {**v, "material_detection_rate": ratio(v["detected_as_material"], v["planted"])}
                            for k, v in sorted(per_kind.items())},
        "overall_material_detection_rate": ratio(sum(v["detected_as_material"] for v in per_kind.values()), planted_total),
        "legitimate_cases_with_material_finding": sum(bool(r["material_kinds"]) for r in clean),
        "legitimate_cases_with_any_finding": sum(bool(r["all_finding_kinds"]) for r in clean),
        "borderline_cases_with_material_finding": sum(bool(r["material_kinds"]) for r in borderline),
        "fraud_cases_without_planted_inconsistency": {r["case_id"]: r["decision"] for r in unplanted_fraud},
        "note": "Fraud cases without a planted inconsistency are consistent-but-fabricated or thin-evidence "
                "dossiers; no dossier-only verifier can establish fraud for them.",
    }


def explanation(case, result, rows_by_engine):
    return {
        "case_id": case["case_id"], "ground_truth": case["ground_truth"], "variant": case["variant"],
        "split": case["split"], "category": case["input"]["category"],
        "adjudication_note": case["adjudication_note"], "expected_action": case["expected_action"],
        "decisions": {engine: rows[case["case_id"]]["decision"] for engine, rows in rows_by_engine.items()},
        "v2_reasons": result.reasons, "v2_influencing_dimensions": result.influencing_dimensions,
        "v2_dimension_scores": result.dimension_scores, "v2_authenticity_score": result.authenticity_score,
        "v2_findings": [{**redact_finding(f), "summary": f.summary, "explanation": f.explanation}
                        for f in result.findings],
        "v2_unmet_requirements": [r.key for r in result.requirements if not r.satisfied],
        "v2_information_requests": result.information_requests,
        "v2_audit_stages": result.audit.stages if result.audit else [],
    }


# ------------------------------------------------------------------ report
def pct(value):
    return "n/a" if value is None else f"{100 * value:.1f}%"


def ci(interval):
    return "" if not interval else f" ({100 * interval[0]:.1f}–{100 * interval[1]:.1f})"


def render_report(report) -> str:
    """Machine-generated tables; every number comes straight from results.json."""
    engines = ["baseline", "candidate_v1", "candidate_v2"]
    m = report["metrics"]
    lines = [f"# Development comparison — {report['run_id']}", "",
             f"Split: **{report['split_evaluated']}** · cases: {report['cases']} · labels: {report['labels']} · "
             f"Gemini calls: {report['gemini_calls_made']} · v2 matches freeze manifest: "
             f"{report['reproducibility']['matches_freeze_manifest']}", "",
             "Fraudulent = positive class; legitimate and borderline = negative. Flag = FLAG_FOR_REVIEW or REJECTED "
             "(legacy engines also: any red flag). NEEDS_MORE_INFORMATION is not a fraud detection. "
             "Brackets: Wilson 95% intervals.", "",
             "## Original vs improved", "", "| Metric | Baseline heuristics | Candidate v1 (original) | Candidate v2 (improved) |",
             "|---|---:|---:|---:|"]
    rows = [("Precision", "precision", "precision_ci95"), ("Recall", "recall", "recall_ci95"), ("F1-score", "f1", None),
            ("False-positive rate", "false_positive_rate", "false_positive_rate_ci95"),
            ("Fraudulent auto-approval rate", "fraudulent_auto_approval_rate", None),
            ("Legitimate auto-approval rate", "legitimate_auto_approval_rate", None),
            ("Manual-review rate (FLAG_FOR_REVIEW)", "manual_review_rate", None),
            ("Needs-more-information rate", "needs_more_information_rate", None),
            ("Rejection rate", "rejection_rate", None), ("Runtime error rate", "runtime_error_rate", None),
            ("Any human follow-up (not approved)", "human_follow_up_rate", None)]
    for title, key, interval in rows:
        lines.append(f"| {title} | " + " | ".join(pct(m[e][key]) + (ci(m[e][interval]) if interval else "")
                                                  for e in engines) + " |")
    lines.append("| Mean latency (ms) | " + " | ".join(f"{m[e]['latency_ms']['mean']:.2f}" for e in engines) + " |")
    lines += ["", "## Confusion matrices (TP / FP / FN / TN)", "", "| Engine | TP | FP | FN | TN |", "|---|---:|---:|---:|---:|"]
    for e in engines:
        c = m[e]["confusion_matrix"]
        lines.append(f"| {e} | {c['true_positive']} | {c['false_positive']} | {c['false_negative']} | {c['true_negative']} |")
    lines += ["", "## Decisions by ground truth", ""]
    for e in engines:
        lines += [f"**{e}**", "", "| Label | " + " | ".join(DECISIONS) + " |", "|---|" + "---:|" * len(DECISIONS)]
        for label, counts in m[e]["decision_matrix"].items():
            lines.append(f"| {label} | " + " | ".join(str(counts[d]) for d in DECISIONS) + " |")
        lines.append("")
    lines += ["## Category-wise", "", "| Category | Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | "
              "Legit approved | NMI rate | TP/FP/FN/TN |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for category in sorted(report["by_category"]["candidate_v2"]):
        for e in engines:
            g = report["by_category"][e][category]
            c = g["confusion_matrix"]
            lines.append(f"| {category} | {e} | {pct(g['precision'])} | {pct(g['recall'])} | {pct(g['f1'])} | "
                         f"{pct(g['false_positive_rate'])} | {pct(g['fraudulent_auto_approval_rate'])} | "
                         f"{pct(g['legitimate_auto_approval_rate'])} | {pct(g['needs_more_information_rate'])} | "
                         f"{c['true_positive']}/{c['false_positive']}/{c['false_negative']}/{c['true_negative']} |")
    lines += ["", "## Split-wise (family-held-out)", "", "| Split | Engine | Precision | Recall | FPR | Legit approved | Cases |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for split in sorted(report["by_split"]["candidate_v2"]):
        for e in engines:
            g = report["by_split"][e][split]
            lines.append(f"| {split} | {e} | {pct(g['precision'])} | {pct(g['recall'])} | {pct(g['false_positive_rate'])} | "
                         f"{pct(g['legitimate_auto_approval_rate'])} | {g['cases']} |")
    lines += ["", "## Ablation (v2 components)", "", "| Configuration | Precision | Recall | F1 | FPR | Fraud auto-approved | "
              "Legit approved | Manual review | NMI |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, g in report["ablation"].items():
        lines.append(f"| {name} | {pct(g['precision'])} | {pct(g['recall'])} | {pct(g['f1'])} | {pct(g['false_positive_rate'])} | "
                     f"{pct(g['fraudulent_auto_approval_rate'])} | {pct(g['legitimate_auto_approval_rate'])} | "
                     f"{pct(g['manual_review_rate'])} | {pct(g['needs_more_information_rate'])} |")
    lines += ["", "## Document-consistency detection (planted contradiction found as a material finding)", "",
              "| Planted kind | Cases | v2 full | without cross-document | without semantic | without category |",
              "|---|---:|---:|---:|---:|---:|"]
    dc = report["document_consistency"]
    for kind, v in dc["candidate_v2"]["by_planted_kind"].items():
        lines.append(f"| {kind} | {v['planted']} | {pct(v['material_detection_rate'])} | "
                     f"{pct(dc['v2_without_cross_document']['by_planted_kind'][kind]['material_detection_rate'])} | "
                     f"{pct(dc['v2_without_semantic']['by_planted_kind'][kind]['material_detection_rate'])} | "
                     f"{pct(dc['v2_without_category']['by_planted_kind'][kind]['material_detection_rate'])} |")
    full = dc["candidate_v2"]
    lines += ["", f"Overall: {pct(full['overall_material_detection_rate'])}. Legitimate cases with a material finding: "
              f"{full['legitimate_cases_with_material_finding']}; with any finding: {full['legitimate_cases_with_any_finding']}. "
              f"Borderline cases with a material finding: {full['borderline_cases_with_material_finding']}. "
              f"Fraud without a planted contradiction: {full['fraud_cases_without_planted_inconsistency']}.", "",
              "## Robustness to meaning-preserving perturbations (v2)", "", "| Perturbation | Decision agreement | Recall | FPR | Changed cases |",
              "|---|---:|---:|---:|---|"]
    for kind, v in report["robustness"].items():
        changed = ", ".join(f"{c['case_id']} {c['from']}→{c['to']}" for c in v["changed_cases"]) or "—"
        lines.append(f"| {kind} | {pct(v['decision_agreement'])} | {pct(v['metrics']['recall'])} | "
                     f"{pct(v['metrics']['false_positive_rate'])} | {changed} |")
    lines += ["", "## Decisions by scenario variant", "", "| Variant | Baseline | v1 | v2 |", "|---|---|---|---|"]
    for variant, table in report["decisions_by_variant"].items():
        cell = lambda e: ", ".join(f"{k} {n}" for k, n in sorted(table.get(e, {}).items()))
        lines.append(f"| {variant} | {cell('baseline')} | {cell('candidate_v1')} | {cell('candidate_v2')} |")
    lines += ["", "## v2 errors against ground truth", "", "| Case | Label | Variant | Decision | Findings | Unmet requirements |",
              "|---|---|---|---|---|---|"]
    for e in report["v2_errors_vs_ground_truth"]:
        lines.append(f"| {e['case_id']} | {e['ground_truth']} | {e['variant']} | {e['decision']} | "
                     f"{', '.join(e['finding_codes']) or '—'} | {', '.join(e['unmet']) or '—'} |")
    lines += ["", f"v1 runtime error types: {report.get('v1_error_types') or 'none'}. "
              f"v1 cases where retrieval dropped a document: "
              f"{report['v1_retrieval_coverage']['cases_where_some_document_was_not_retrieved']}.", "",
              report["interpretation"], ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------- run
async def run(split="all", output_dir=None, require_frozen=False):
    current = package_digest()
    manifest = json.loads(FREEZE_MANIFEST.read_text()) if FREEZE_MANIFEST.exists() else None
    frozen_match = bool(manifest and manifest["v2_package"]["combined"] == current["combined"])
    if require_frozen and not frozen_match:
        raise SystemExit("v2 code differs from the freeze manifest; refusing a frozen evaluation run")
    cases = load_cases(split)

    settings.GEMINI_API_KEY = ""
    ai_verifier.api_key = ""
    calls = {"gemini": 0}
    original_post = gemini_api.post_json

    async def guarded_post(*args, **kwargs):
        calls["gemini"] += 1
        raise RuntimeError("Gemini call attempted during offline evaluation")
    gemini_api.post_json = guarded_post
    rag.post_json = guarded_post

    try:
        baseline = await run_baseline(cases)
        with tempfile.TemporaryDirectory(prefix="sevafund-dev-v2-") as scratch:
            directory = Path(scratch)
            rag.UPLOAD_DIR = directory
            references = materialize(cases, directory)
            v1 = await run_v1(cases, references, directory)
            v2_rows, details = run_v2(cases, references, directory, ABLATIONS["full"], keep_detail=True)
            ablations = {name: run_v2(cases, references, directory, config)[0]
                         for name, config in ABLATIONS.items() if name != "full"}
        robustness = {}
        for kind in PERTURBATIONS:
            perturbed = [perturb_case(c, kind) for c in cases]
            with tempfile.TemporaryDirectory(prefix=f"sevafund-dev-v2-{kind}-") as scratch:
                directory = Path(scratch)
                references = materialize(perturbed, directory)
                rows, _ = run_v2(perturbed, references, directory, ABLATIONS["full"])
            reference = {r["case_id"]: r["decision"] for r in v2_rows}
            changed = [{"case_id": r["case_id"], "variant": r["variant"], "from": reference[r["case_id"]],
                        "to": r["decision"]} for r in rows if r["decision"] != reference[r["case_id"]]]
            robustness[kind] = {"decision_agreement": ratio(len(rows) - len(changed), len(rows)),
                                "metrics": metrics(rows), "changed_cases": changed}
    finally:
        gemini_api.post_json = original_post
        rag.post_json = original_post
    if calls["gemini"]:
        raise SystemExit("A Gemini request was attempted; offline evaluation invalid")

    ids = [r["case_id"] for r in baseline]
    for rows in [v1, v2_rows, *ablations.values()]:
        if sorted(r["case_id"] for r in rows) != sorted(ids):
            raise ValueError("Engines did not receive identical case sets")

    engines = {"baseline": baseline, "candidate_v1": v1, "candidate_v2": v2_rows}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output_dir or Path(__file__).with_name("runs") / f"development_candidate_v2_{split}_{stamp}"
    target.mkdir(parents=True, exist_ok=False)

    by_engine = {name: {r["case_id"]: r for r in rows} for name, rows in engines.items()}
    by_engine.update({f"v2_{name}": {r["case_id"]: r for r in rows} for name, rows in ablations.items()})
    case_by_id = {c["case_id"]: c for c in cases}
    with (target / "explanations.jsonl").open("w", encoding="utf-8") as handle:
        for case_id in ids:
            handle.write(json.dumps(explanation(case_by_id[case_id], details[case_id], by_engine), ensure_ascii=False) + "\n")
    with (target / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["case_id", "ground_truth", "category", "split", "scenario_family", "variant", "expected_action",
                  *[f"{name}_decision" for name in by_engine], "v2_finding_codes", "v2_unmet_requirements",
                  "baseline_latency_ms", "candidate_v1_latency_ms", "candidate_v2_latency_ms"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case_id in ids:
            row = by_engine["candidate_v2"][case_id]
            writer.writerow({**{k: row[k] for k in fields[:7]},
                             **{f"{name}_decision": rows[case_id]["decision"] for name, rows in by_engine.items()},
                             "v2_finding_codes": ";".join(row["finding_codes"]),
                             "v2_unmet_requirements": ";".join(row["unmet_requirements"]),
                             **{f"{name}_latency_ms": round(by_engine[name][case_id]["latency_ms"], 3)
                                for name in engines}})

    variant_table = defaultdict(lambda: defaultdict(Counter))
    for name in engines:
        for row in by_engine[name].values():
            variant_table[row["variant"]][name][row["decision"]] += 1
    report = {
        "run_id": target.name, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_evaluated": split, "dataset": DATASET.name, "dataset_sha256": digest(DATASET), "synthetic": True,
        "cases": len(cases), "labels": dict(Counter(c["ground_truth"] for c in cases)),
        "evaluation_mode": "Offline deterministic engines; Gemini generation, embeddings and OCR disabled and guarded",
        "gemini_calls_made": calls["gemini"],
        "positive_class": "fraudulent; legitimate and borderline are negative",
        "flag_definition": "FLAG_FOR_REVIEW or REJECTED (legacy engines: also any emitted red flag). "
                           "NEEDS_MORE_INFORMATION is never counted as a fraud detection in primary metrics.",
        "input_paths": {"baseline": "AIVerifierService fallback with lexical top-5 retrieval",
                        "candidate_v1": "top-5 lexically retrieved chunks (its frozen protocol)",
                        "candidate_v2": "every uploaded document, extracted in full with rag.extract_document_text"},
        "v1_retrieval_coverage": {"cases_with_documents": sum(r["document_count"] > 0 for r in v1),
                                  "cases_where_some_document_was_not_retrieved":
                                      sum(r["retrieved_chunks"] < r["document_count"] for r in v1)},
        "metrics": {name: metrics(rows) for name, rows in engines.items()},
        "by_category": {name: grouped(rows, "category") for name, rows in engines.items()},
        "by_split": {name: grouped(rows, "split") for name, rows in engines.items()},
        "by_family_v2": grouped(v2_rows, "scenario_family"),
        "decisions_by_variant": {v: {e: dict(c) for e, c in table.items()} for v, table in sorted(variant_table.items())},
        "ablation": {"full": metrics(v2_rows), **{name: metrics(rows) for name, rows in ablations.items()}},
        "ablation_by_category": {name: grouped(rows, "category")
                                 for name, rows in {"full": v2_rows, **ablations}.items()},
        "document_consistency": {name: consistency_report(cases, rows)
                                 for name, rows in {"candidate_v2": v2_rows, **{f"v2_{k}": v for k, v in ablations.items()}}.items()},
        "robustness": robustness,
        "v2_errors_vs_ground_truth": [
            {"case_id": r["case_id"], "ground_truth": r["ground_truth"], "variant": r["variant"],
             "decision": r["decision"], "finding_codes": r["finding_codes"], "unmet": r["unmet_requirements"]}
            for r in v2_rows if (r["ground_truth"] == "fraudulent") != r["flagged"]
            or (r["ground_truth"] == "legitimate" and r["decision"] != "APPROVED")],
        "reproducibility": {
            "python": sys.version.split()[0], "engine_version": ENGINE_VERSION,
            "config": ABLATIONS["full"].model_dump(), "config_digest": ABLATIONS["full"].digest(),
            "v2_package": current, "matches_freeze_manifest": frozen_match,
            "candidate_v1_sha256": digest(ROOT / "app/services/development_verifier.py"),
            "baseline_verifier_sha256": digest(ROOT / "app/services/ai_verifier.py"),
            "fraud_rules_sha256": digest(ROOT / "app/services/fraud_detector.py"),
            "rag_sha256": digest(ROOT / "app/services/rag.py"),
            "generator_sha256": digest(Path(__file__).with_name("generate_development_dataset_v2.py")),
            "runner_sha256": digest(Path(__file__)),
            "perturbations_sha256": digest(Path(__file__).with_name("perturbations.py")),
        },
        "interpretation": "Synthetic development corpus authored together with the candidate. Results show "
                          "behaviour on these scenario designs only and are not estimates of real-world accuracy.",
    }
    report["v1_error_types"] = dict(Counter(r["error_type"] for r in v1 if r.get("error_type")))
    (target / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "run_config.json").write_text(json.dumps(report["reproducibility"], indent=2) + "\n", encoding="utf-8")
    (target / "report.md").write_text(render_report(report), encoding="utf-8")
    summary = {name: {k: m[k] for k in ("precision", "recall", "f1", "false_positive_rate",
                                         "fraudulent_auto_approval_rate", "legitimate_auto_approval_rate",
                                         "manual_review_rate", "needs_more_information_rate", "runtime_error_rate")}
               for name, m in report["metrics"].items()}
    print(json.dumps({"run_id": target.name, "results": str(target / "results.json"), "summary": summary,
                      "robustness": {k: v["decision_agreement"] for k, v in robustness.items()},
                      "matches_freeze_manifest": frozen_match}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["tune", "validation", "all"], default="all")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--require-frozen", action="store_true",
                        help="Refuse to run unless the v2 package matches the freeze manifest")
    args = parser.parse_args()
    asyncio.run(run(args.split, args.output_dir, args.require_frozen))
