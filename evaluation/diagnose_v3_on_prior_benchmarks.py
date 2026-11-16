"""One-time diagnostic of FROZEN V3 on the previously used 200-, 100- and 150-case corpora.

These are previously used diagnostic datasets, NOT fresh independent tests:
the 150-case set motivated V2, all three motivated V3, and individual cases
appear in regression tests.  Nothing may be changed in response to this run.

Engines and provenance of their predictions:
  V3        - executed here, once (frozen; the freeze is verified first).
  V2        - saved predictions of frozen V2 (runs/diagnostic_v2_prior_benchmarks_20261115T205120Z).
  V1        - 150: saved (runs/independent_test_150_20261115T170654Z);
              200 and 100: executed here on frozen V1 (hash-verified), its top-5 lexical-retrieval protocol,
              because no saved paired V1 run existed.
  baseline  - saved predictions of the frozen heuristic verifier (same source hashes as today).
Gemini is disabled and guarded; no API call is possible.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.services import gemini_api, rag
from app.services.ai_verifier import ai_verifier
from app.services.development_verifier import verify_development_case
from app.services.development_verifier_v3 import verify_case as verify_v3
from app.services.development_verifier_v3.config import DEFAULT_CONFIG as V3_CONFIG
from app.services.fraud_detector import format_inr
from evaluate_development_candidate_v2 import FREEZE_MANIFEST as V2_MANIFEST, package_digest as v2_digest
from evaluate_development_verifier_v3 import v3_input
from evaluate_independent_test_150 import assert_frozen
from group_uncertainty import case_metrics, group_report
from verify_candidate_v3_freeze import verify as verify_v3_freeze
from workflow_metrics import workflow_metrics

RUNS = Path(__file__).with_name("runs")
DATASETS = {
    "fundraising_200": {"file": "fundraising_scenarios.jsonl", "group": "scenario_group",
                        "baseline": ("csv", "offline_heuristic_lexical_200_20261115T150208Z/predictions.csv"),
                        "v1": None,
                        "note": "The baseline heuristic rules were revised after reviewing their errors on this very "
                                "set (evaluation/README.md), so the baseline row is in-sample and overstates it."},
    "independent_benchmark_100": {"file": "independent_benchmark_100.jsonl", "group": "scenario_group",
                                  "baseline": ("csv", "independent_benchmark_100_offline_20261115T153504Z/predictions.csv"),
                                  "v1": None,
                                  "note": "Every case is its own scenario group, so clusters equal cases here."},
    "independent_test_150": {"file": "independent_test_150.jsonl", "group": "scenario_family",
                             "baseline": ("json", "independent_test_150_20261115T170654Z/baseline.json"),
                             "v1": ("json", "independent_test_150_20261115T170654Z/candidate.json"),
                             "note": "This set motivated V2; four of its cases are V2/V3 crash-regression tests."},
}
V2_SAVED = "diagnostic_v2_prior_benchmarks_20261115T205120Z/results.json"
LEGACY = {"AUTO_APPROVE": "APPROVED", "NEEDS_MORE_INFO": "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW": "FLAG_FOR_REVIEW",
          "REJECT": "REJECTED", "SYSTEM_ERROR": "VERIFICATION_ERROR"}
ENGINES = ["baseline", "V1", "V2", "V3"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def truthy(value) -> bool:
    return value is True or str(value).strip().lower() == "true"


def load_saved(kind, relative):
    path = RUNS / relative
    if kind == "csv":
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))["predictions"]
    return {r["case_id"]: {"decision": LEGACY.get(r["recommendation"], r["recommendation"]),
                           "flagged": truthy(r["flagged"])} for r in rows}, sha(path)


async def run_v1(cases):
    """Frozen V1 on its original protocol: lexical top-5 retrieval, then the V1 rules."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="sevafund-v1-prior-") as scratch:
        directory = Path(scratch)
        rag.UPLOAD_DIR = directory
        for case in cases:
            data = case["input"]
            references = []
            for index, document in enumerate(data.get("documents", []), start=1):
                name = f"{case['case_id'].lower()}-{index}.txt"
                (directory / name).write_text(document["content"], encoding="utf-8")
                references.append({"doc_type": document["doc_type"], "title": document["title"],
                                   "file_url": f"/private-documents/{name}"})
            query = " ".join([data["title"], data["category"], data.get("beneficiary_name") or "",
                              f"{data.get('city', '')}, {data.get('state', '')}".strip(", "), data["story"],
                              format_inr(data["goal_amount"])])
            started = time.perf_counter()
            retrieved = await rag.retrieve_evidence(references, query, top_k=5)
            try:
                output = verify_development_case(data["title"], data["category"], data["story"], data["goal_amount"],
                                                 beneficiary_name=data.get("beneficiary_name"),
                                                 documents=[chunk["text"] for chunk in retrieved])
                decision = LEGACY[output.result.recommendation]
                flagged = decision in {"FLAG_FOR_REVIEW", "REJECTED"} or bool(output.result.red_flags)
                error = None
            except Exception as exc:            # frozen V1 evaluated as-is
                decision, flagged, error = "VERIFICATION_ERROR", False, type(exc).__name__
            out[case["case_id"]] = {"decision": decision, "flagged": flagged, "error_type": error,
                                    "latency_ms": (time.perf_counter() - started) * 1000}
    return out


def run_v3(cases):
    out = {}
    for case in cases:
        started = time.perf_counter()
        try:
            result = verify_v3(v3_input(case["input"]), V3_CONFIG)
            decision, codes, error = result.decision.value, sorted({f.code for f in result.findings}), None
            critical = [r.key for r in result.requirements if getattr(r, "critical", True) and not r.satisfied]
        except Exception as exc:                # never expected; recorded, never approved
            decision, codes, critical, error = "VERIFICATION_ERROR", [], [], type(exc).__name__
        out[case["case_id"]] = {"decision": decision, "flagged": decision in {"FLAG_FOR_REVIEW", "REJECTED"},
                                "finding_codes": codes, "critical_missing": critical, "error_type": error,
                                "latency_ms": (time.perf_counter() - started) * 1000}
    return out


def by_category(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    return {name: case_metrics(group) for name, group in sorted(groups.items())}


def pct(value):
    return "n/a" if value is None else f"{100 * value:.1f}%"


def ci(interval):
    return "" if not interval else f" ({100 * interval[0]:.0f}–{100 * interval[1]:.0f})"


def render(report) -> str:
    lines = ["# Frozen V3 on previously used diagnostic benchmarks", "",
             "**These are previously used diagnostic datasets, not fresh independent tests.** All three were "
             "examined during earlier development cycles; they are synthetic and single-author. V3 was run once "
             "here and was not changed afterwards. Gemini disabled (0 calls).", "",
             "Fraud is the positive class; legitimate **and borderline** cases are negatives (the convention the "
             "original protocols for these datasets used). A detection is FLAG_FOR_REVIEW or REJECTED (baseline and "
             "V1 also count any emitted red flag, as in their original evaluations). Information requests are not "
             "detections.", ""]
    for name, data in report["datasets"].items():
        lines += [f"## {name} ({data['cases']} cases; {data['label_clusters']} label clusters)", "",
                  f"*Note: {data['note']}*", "",
                  "| Engine | Source | Precision | Recall | F1 | FPR | Legit FPR | Fraud auto-approved | Legit approved | "
                  "Manual review | Info request | Reject | Runtime errors |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for engine in ENGINES:
            m = data["engines"][engine]["metrics"]
            lines.append(f"| {engine} | {data['engines'][engine]['source']} | {pct(m['precision'])} | {pct(m['recall'])} | "
                         f"{pct(m['f1'])} | {pct(m['false_positive_rate'])} | {pct(m['legitimate_false_positive_rate'])} | "
                         f"{pct(m['fraudulent_auto_approval_rate'])} | {pct(m['legitimate_auto_approval_rate'])} | "
                         f"{pct(m['manual_review_rate'])} | {pct(m['information_request_rate'])} | "
                         f"{pct(m['rejection_rate'])} | {pct(m['runtime_error_rate'])} |")
        lines += ["", "Category-wise recall / legitimate approval:", "",
                  "| Category | " + " | ".join(ENGINES) + " |", "|---|" + "---|" * len(ENGINES)]
        for category in sorted(data["engines"]["V3"]["by_category"]):
            cells = []
            for engine in ENGINES:
                g = data["engines"][engine]["by_category"][category]
                cells.append(f"{pct(g['recall'])} / {pct(g['legitimate_auto_approval_rate'])}")
            lines.append(f"| {category} | " + " | ".join(cells) + " |")
        g = data["engines"]["V3"]["group"]
        cl = g["cluster_level"]
        lines += ["", f"V3 group level: {g['homogeneous_clusters']}/{g['label_clusters']} clusters homogeneous; "
                  f"detection ICC {g['detection_icc']}; effective n ≈ {g['effective_sample_size_for_detection']}. "
                  f"Fraud clusters flagged {cl['fraud_clusters_flagged']['hits']}/{cl['fraud_clusters_flagged']['clusters']}"
                  f"{ci(cl['fraud_clusters_flagged']['ci95'])}; recall cluster-bootstrap 95% CI "
                  f"{ci(g['cluster_bootstrap_ci95']['recall'])}.", ""]
        w = data["engines"]["V3"]["workflow"]
        lines += [f"V3 under the pending-confirmation workflow: states {w['state_counts']}. "
                  f"Safety — automatic activations {w['approval_safety']['automatic_activations']}, fraud pending "
                  f"external confirmation {w['approval_safety']['fraud_pending_external_confirmation']}. Workload — "
                  f"{w['administrative_workload']['manual_reviews']} reviews, "
                  f"{w['administrative_workload']['information_requests']} information requests, "
                  f"{w['administrative_workload']['external_confirmations_required']} external confirmations.", ""]
        lines += [f"V3 critical-evidence gaps behind information requests: {data['v3_critical_missing_top']}", ""]
    lines += ["## Provenance", "", json.dumps(report["provenance"], indent=2), ""]
    return "\n".join(lines)


async def main(output_dir=None):
    freeze = verify_v3_freeze()
    if not freeze["valid"]:
        raise SystemExit(f"V3 freeze invalid: {freeze['checks']}")
    v2_manifest = json.loads(V2_MANIFEST.read_text())
    if v2_manifest["v2_package"]["combined"] != v2_digest()["combined"]:
        raise SystemExit("V2 differs from its freeze manifest")
    frozen_components = assert_frozen()          # V1, baseline verifier, rules, rag, config, schema
    target = output_dir or RUNS / f"diagnostic_v3_prior_benchmarks_{freeze['v3_package_sha256'][:12]}"
    if target.exists():
        raise SystemExit(f"{target} exists: this diagnostic is one-time; refusing to re-run")

    settings.GEMINI_API_KEY = ""
    ai_verifier.api_key = ""
    calls = {"n": 0}

    async def guarded(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("Gemini call attempted during offline diagnostic")
    gemini_api.post_json = guarded
    rag.post_json = guarded

    v2_saved = json.loads((RUNS / V2_SAVED).read_text())["corpora"]
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "datasets": {}, "provenance": {
        "v3_package_sha256": freeze["v3_package_sha256"], "v3_config_sha256": freeze["config_sha256"],
        "v2_package_sha256": v2_manifest["v2_package"]["combined"], "frozen_v1_and_baseline": frozen_components,
        "v2_saved_predictions": {"path": V2_SAVED, "sha256": sha(RUNS / V2_SAVED)},
        "runner_sha256": sha(Path(__file__)), "python": sys.version.split()[0]}}
    case_rows = []
    for name, spec in DATASETS.items():
        path = Path(__file__).with_name(spec["file"])
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        predictions, sources = {}, {}
        predictions["baseline"], baseline_hash = load_saved(*spec["baseline"])
        sources["baseline"] = f"saved ({spec['baseline'][1].split('/')[0]})"
        if spec["v1"]:
            predictions["V1"], _ = load_saved(*spec["v1"])
            sources["V1"] = f"saved ({spec['v1'][1].split('/')[0]})"
        else:
            predictions["V1"] = await run_v1(cases)
            sources["V1"] = "executed here (frozen V1)"
        predictions["V2"] = {r["case_id"]: {"decision": r["decision"], "flagged": r["flagged"]}
                             for r in v2_saved[name]["predictions"]}
        sources["V2"] = "saved (diagnostic_v2_prior_benchmarks)"
        predictions["V3"] = run_v3(cases)
        sources["V3"] = "executed here once (frozen V3)"
        ids = [c["case_id"] for c in cases]
        for engine in ENGINES:
            if sorted(predictions[engine]) != sorted(ids):
                raise ValueError(f"{name}: {engine} does not cover exactly the dataset's case IDs")
        engines = {}
        for engine in ENGINES:
            rows = [{"case_id": c["case_id"], "ground_truth": c["ground_truth"], "category": c["input"]["category"],
                     "beneficiary_type": c["input"].get("beneficiary_type"), "cluster": c.get(spec["group"]),
                     **predictions[engine][c["case_id"]]} for c in cases]
            engines[engine] = {"source": sources[engine], "metrics": case_metrics(rows),
                               "metrics_borderline_excluded": case_metrics(rows, include_borderline_as_negative=False),
                               "by_category": by_category(rows), "group": group_report(rows)}
            if engine == "V3":
                engines[engine]["workflow"] = workflow_metrics(rows)
            for row in rows:
                case_rows.append({"dataset": name, "engine": engine, **{k: row.get(k) for k in (
                    "case_id", "ground_truth", "category", "cluster", "decision", "flagged", "finding_codes",
                    "critical_missing", "error_type")}})
        missing = Counter(k for r in predictions["V3"].values() if r["decision"] == "NEEDS_MORE_INFORMATION"
                          for k in r["critical_missing"])
        report["datasets"][name] = {"dataset_sha256": sha(path), "cases": len(cases), "note": spec["note"],
                                    "label_clusters": engines["V3"]["group"]["label_clusters"],
                                    "baseline_source_sha256": baseline_hash, "engines": engines,
                                    "v3_critical_missing_top": dict(missing.most_common(6))}
    if calls["n"]:
        raise SystemExit("A Gemini call was attempted; diagnostic invalid")
    report["gemini_calls_made"] = 0
    target.mkdir(parents=True)          # created only after every engine completed
    (target / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
    with (target / "case_level_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(case_rows[0]))
        writer.writeheader()
        writer.writerows(case_rows)
    (target / "report.md").write_text(render(report), encoding="utf-8")
    print(json.dumps({"output": str(target), "summary": {
        name: {engine: {k: d["engines"][engine]["metrics"][k] for k in (
            "precision", "recall", "false_positive_rate", "fraudulent_auto_approval_rate",
            "legitimate_auto_approval_rate", "information_request_rate", "runtime_error_rate")} for engine in ENGINES}
        for name, d in report["datasets"].items()}}, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path)
    asyncio.run(main(parser.parse_args().output_dir))
