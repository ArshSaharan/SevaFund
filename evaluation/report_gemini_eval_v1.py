"""Report for the controlled 10-group Gemini evaluation (v1).  Reads saved results only; makes no API call.

Sections 1-10 are generated from the experiment's cache/failures/state, the selection manifest, the pre-run
freeze record and the earlier pilot comparison.  The interpretation and recommendation (section 11) are
supplied by the analyst in a separate Markdown file so that every number in the report is machine-generated.

Fraud is the positive class. A detection is FLAG_FOR_REVIEW or REJECTED only; NEEDS_MORE_INFORMATION and
ELIGIBLE_PENDING_CONFIRMATION are never detections.  Diagnostic results on previously available synthetic data.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_evaluation_framework as fw
from app.services.development_approval_workflow import AutomatedOutcome, start
from group_uncertainty import wilson

RUNS = Path(__file__).with_name("runs")
SYSTEMS = ["heuristics_only", "heuristics_lexical", "gemini_no_rag", "gemini_rag", "v3", "hybrid"]
TITLES = {"heuristics_only": "Heuristics, no documents", "heuristics_lexical": "Deterministic fallback (heuristics + lexical retrieval)",
          "gemini_no_rag": "Gemini 3.6 Flash, no documents", "gemini_rag": "Gemini 3.6 Flash + RAG",
          "v3": "Frozen V3", "hybrid": "Frozen V3 + Gemini (combined)"}
DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}
DECISIONS = ["APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR", "NOT_RUN"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(v):
    return "n/a" if v is None else f"{100 * v:.0f}%"


def ci(v):
    return "" if not v else f" ({100 * v[0]:.0f}–{100 * v[1]:.0f}%)"


def nearest_rank(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else None


def load_experiment(directory: Path):
    cache = [json.loads(l) for l in (directory / "cache.jsonl").read_text().splitlines() if l.strip()]
    failures = [json.loads(l) for l in (directory / "failures.jsonl").read_text().splitlines() if l.strip()] \
        if (directory / "failures.jsonl").exists() else []
    state = json.loads((directory / "state.json").read_text()) if (directory / "state.json").exists() else {}
    results = {(r["config"], r["case_id"]): r for r in cache if r.get("stage") == "result"}
    retrieval = {r["case_id"]: r for r in cache if r.get("stage") == "retrieval"}
    return results, retrieval, failures, state


def decision_of(system, case_id, results):
    if system == "v3":
        hybrid = results.get(("hybrid", case_id))
        return hybrid["v3_decision"] if hybrid else "NOT_RUN"
    record = results.get((system, case_id))
    return record["decision"] if record else "NOT_RUN"


def metrics(rows):
    """rows: dicts with label, decision.  Negatives = legitimate + borderline."""
    fraud = [r for r in rows if r["label"] == "fraudulent"]
    negatives = [r for r in rows if r["label"] != "fraudulent"]
    legit = [r for r in rows if r["label"] == "legitimate"]
    tp = sum(r["decision"] in DETECT for r in fraud)
    fp = sum(r["decision"] in DETECT for r in negatives)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / len(fraud) if fraud else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else (0.0 if precision is not None else None)
    count = lambda group, *ds: sum(r["decision"] in ds for r in group)
    return {
        "evaluated": sum(r["decision"] != "NOT_RUN" for r in rows),
        "tp": tp, "fp": fp, "fn": len(fraud) - tp, "tn": len(negatives) - fp,
        "precision": precision, "precision_ci": wilson(tp, tp + fp), "recall": recall, "recall_ci": wilson(tp, len(fraud)),
        "f1": f1, "fpr": fp / len(negatives) if negatives else None, "fpr_ci": wilson(fp, len(negatives)),
        "legit_fpr": count(legit, *DETECT) / len(legit) if legit else None,
        "fraud_review_flags": count(fraud, "FLAG_FOR_REVIEW"), "fraud_rejections": count(fraud, "REJECTED"),
        "rejections_total": count(rows, "REJECTED"),
        "info_requests": {lab: count([r for r in rows if r["label"] == lab], "NEEDS_MORE_INFORMATION")
                          for lab in ("legitimate", "fraudulent", "borderline")},
        "approved_held_pending": {lab: count([r for r in rows if r["label"] == lab], "APPROVED")
                                  for lab in ("legitimate", "fraudulent", "borderline")},
        "legit_escalated": count(legit, *DETECT), "legit_info_requests": count(legit, "NEEDS_MORE_INFORMATION"),
        "fraud_missed": {"approved_then_held": count(fraud, "APPROVED"), "information_request": count(fraud, "NEEDS_MORE_INFORMATION"),
                         "not_run_or_error": count(fraud, "NOT_RUN", "VERIFICATION_ERROR")},
        "matrix": {lab: dict(Counter(r["decision"] for r in rows if r["label"] == lab)) for lab in ("legitimate", "fraudulent", "borderline")},
        "not_run_or_error_all": count(rows, "NOT_RUN", "VERIFICATION_ERROR"),
    }


def correct_direction(label, decision):
    return {"fraudulent": decision in DETECT, "legitimate": decision == "APPROVED",
            "borderline": decision in ("NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW")}[label]


def build(experiment: Path, selection: Path, pilot_comparison: Path, freeze: Path):
    sel = json.loads(selection.read_text())
    cases = {c["case_id"]: c for c in sel["cases"]}
    data = {json.loads(l)["case_id"]: json.loads(l) for l in (selection.parent / "cases.jsonl").read_text().splitlines() if l.strip()}
    results, retrieval, failures, state = load_experiment(experiment)
    rows = {s: [{"case_id": cid, "label": c["label"], "category": c["category"], "decision": decision_of(s, cid, results)}
                for cid, c in cases.items()] for s in SYSTEMS}
    for s in SYSTEMS:
        for row in rows[s]:
            if row["decision"] == "APPROVED":
                row["workflow_state"] = start(AutomatedOutcome(decision="APPROVED", category=row["category"])).state.value
    generation_ok = [r for (c, _), r in results.items() if c in ("gemini_no_rag", "gemini_rag")]
    latencies = [r["generation_latency_ms"] / 1000 for r in generation_ok]
    gen_failures = [f for f in failures if f["stage"] == "generation"]
    pre = json.loads(freeze.read_text())
    post_hashes = {f: sha(ROOT / f) for f in pre["files"]}
    # production default model is read without the evaluation-only override
    default_model = subprocess.run([sys.executable, "-c", "from app.config import settings; print(settings.GEMINI_MODEL)"],
                                   capture_output=True, text=True, cwd=ROOT,
                                   env={k: v for k, v in __import__("os").environ.items() if k != "GEMINI_MODEL"}).stdout.strip()
    per_case = []
    for cid, c in cases.items():
        g_rag, g_no = results.get(("gemini_rag", cid)), results.get(("gemini_no_rag", cid))
        hybrid = results.get(("hybrid", cid))
        chunks = (retrieval.get(cid) or {}).get("chunks", [])
        lexical = [x["title"] for x in fw.lexical_retrieve(data[cid])]
        per_case.append({
            "case_id": cid, "group": c["group"], "category": c["category"], "label": c["label"],
            "selection_reason": c["selection_reason"], "keyword_free": not c["matches_known_red_flag_lexicon"],
            "retrieved": [{"title": x["title"], "score": x["relevance"]} for x in chunks],
            "lexical_titles": lexical,
            **{f"{s}_decision": decision_of(s, cid, results) for s in SYSTEMS},
            "gemini_rag_risk": g_rag and g_rag.get("risk_level"), "gemini_rag_summary": g_rag and g_rag.get("summary"),
            "gemini_rag_red_flags": g_rag and g_rag.get("red_flag_texts"),
            "gemini_rag_missing": g_rag and g_rag.get("missing_requirements"),
            "gemini_no_rag_summary": g_no and g_no.get("summary"), "gemini_no_rag_red_flags": g_no and g_no.get("red_flag_texts"),
            "gemini_rag_latency_s": g_rag and round(g_rag["generation_latency_ms"] / 1000, 2),
            "gemini_no_rag_latency_s": g_no and round(g_no["generation_latency_ms"] / 1000, 2),
            "v3_reasons": hybrid and hybrid.get("v3_reasons"), "v3_finding_codes": hybrid and hybrid.get("v3_finding_codes"),
            "hybrid_workflow_state": hybrid and hybrid.get("workflow_state"),
            "escalated_by_gemini": hybrid and hybrid.get("escalated_by_gemini"),
            "api_errors": [f"{f['config']}:{f['stage']}:{f['category']}" for f in failures if f["case_id"] == cid],
        })
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "experiment": experiment.name,
        "classification": sel["classification"], "selection": sel["cases"],
        "integrity": {"git_commit_before": pre["git_head"], "working_tree_clean_before": pre["working_tree_clean"],
                      "files_hashed": len(pre["files"]), "files_unchanged_after_run": post_hashes == pre["files"],
                      "changed_files": [f for f in pre["files"] if post_hashes[f] != pre["files"][f]],
                      "production_default_model": default_model, "evaluation_model": next(iter({r.get("model") for r in generation_ok}), None)},
        "api": {"cumulative_calls": state.get("cumulative_calls", {}), "budget": {"generation": 20, "embedding": 10},
                "stopped_reason": state.get("stopped_reason"), "failures": failures},
        "reliability": {"generation_attempted": len(generation_ok) + len(gen_failures), "generation_succeeded": len(generation_ok),
                        "timeouts": sum(f["category"].endswith("TIMEOUT") for f in gen_failures),
                        "server_errors": sum(f["category"] == "SERVER_ERROR" for f in gen_failures),
                        "other_failures": dict(Counter(f["category"] for f in gen_failures
                                                       if not f["category"].endswith("TIMEOUT") and f["category"] != "SERVER_ERROR")),
                        "success_ci": wilson(len(generation_ok), len(generation_ok) + len(gen_failures)),
                        "latency_s": {"n": len(latencies), "mean": statistics.mean(latencies) if latencies else None,
                                      "median": statistics.median(latencies) if latencies else None,
                                      "p95_nearest_rank": nearest_rank(latencies, .95), "max": max(latencies) if latencies else None},
                        "embedding_latency_s": [round(r["latency_ms"] / 1000, 2) for r in retrieval.values()]},
        "metrics": {s: metrics(rows[s]) for s in SYSTEMS},
        "per_case": per_case,
        "pilots": json.loads(pilot_comparison.read_text()) if pilot_comparison.exists() else None,
    }
    # Phase-5 questions, computed
    by = {p["case_id"]: p for p in per_case}
    fraud_ids = [c for c, v in cases.items() if v["label"] == "fraudulent"]
    report["contribution"] = {
        "fraud_flagged_by_gemini_rag_but_not_v3": [c for c in fraud_ids if by[c]["gemini_rag_decision"] in DETECT and by[c]["v3_decision"] not in DETECT],
        "fraud_flagged_by_gemini_rag_but_not_fallback": [c for c in fraud_ids if by[c]["gemini_rag_decision"] in DETECT and by[c]["heuristics_lexical_decision"] not in DETECT],
        "rag_vs_no_rag_correct_direction": {
            "rag_only": [c for c in cases if correct_direction(cases[c]["label"], by[c]["gemini_rag_decision"]) and not correct_direction(cases[c]["label"], by[c]["gemini_no_rag_decision"])],
            "no_rag_only": [c for c in cases if correct_direction(cases[c]["label"], by[c]["gemini_no_rag_decision"]) and not correct_direction(cases[c]["label"], by[c]["gemini_rag_decision"])],
            "both": [c for c in cases if correct_direction(cases[c]["label"], by[c]["gemini_rag_decision"]) and correct_direction(cases[c]["label"], by[c]["gemini_no_rag_decision"])]},
        "legit_flagged_by_gemini_rag": [c for c in cases if cases[c]["label"] == "legitimate" and by[c]["gemini_rag_decision"] in DETECT],
        "consistent_fabrication_case": {c: by[c]["gemini_rag_decision"] for c in fraud_ids if "consistent" in cases[c]["group"] or "forged" in cases[c]["group"]},
        "unsafe_approvals_fraud_or_borderline": {s: [c for c in cases if cases[c]["label"] != "legitimate" and by[c][f"{s}_decision"] == "APPROVED"] for s in ("v3", "hybrid", "gemini_rag", "heuristics_lexical")},
        "manual_reviews": {s: sum(by[c][f"{s}_decision"] == "FLAG_FOR_REVIEW" for c in cases) for s in SYSTEMS},
    }
    report["disagreements"] = [
        {"case_id": c, "label": cases[c]["label"], "pair": f"{a} vs {b}", "a": by[c][f"{a}_decision"], "b": by[c][f"{b}_decision"]}
        for c in cases for a, b in (("gemini_rag", "heuristics_lexical"), ("gemini_rag", "v3"), ("gemini_rag", "gemini_no_rag"), ("hybrid", "v3"))
        if by[c][f"{a}_decision"] != by[c][f"{b}_decision"]]
    return report


def render(report, interpretation: str) -> str:
    m = report["metrics"]
    rel = report["reliability"]
    lat = rel["latency_s"]
    api = report["api"]
    L = [f"# Controlled Gemini 3.6 Flash evaluation — 10 scenario groups ({report['experiment']})", "",
         f"> **{report['classification']}** Synthetic, single-author data; 10 cases. These results do not establish "
         "real-world accuracy or production readiness.", "",
         "## 1. Executive summary", "",
         f"* Gemini generation: {rel['generation_succeeded']}/{rel['generation_attempted']} succeeded "
         f"(Wilson 95% {pct(rel['success_ci'][0]) if rel['success_ci'] else 'n/a'}–{pct(rel['success_ci'][1]) if rel['success_ci'] else 'n/a'}); "
         f"{rel['timeouts']} timeouts, {rel['server_errors']} server errors; mean latency "
         f"{lat['mean']:.1f} s, p95 {lat['p95_nearest_rank']:.1f} s." if lat["mean"] is not None else "* No successful generation.",
         f"* API requests used: {api['cumulative_calls']} of the approved budget {api['budget']}; stop reason: {api['stopped_reason']}.",
         "* Fraud detection (FLAG/REJECT only), recall on 4 fraud cases: " +
         "; ".join(f"{TITLES[s]} {m[s]['tp']}/4" for s in SYSTEMS) + ".",
         "* Legitimate campaigns escalated to review/rejection: " + "; ".join(f"{TITLES[s]} {m[s]['legit_escalated']}/4" for s in SYSTEMS) + ".",
         "* See section 11 for the interpretation and recommendation.", "",
         "## 2. Dataset and scenario-group selection", "",
         "| Case | Group | Category | Label | Keyword-free | Selection reason |", "|---|---|---|---|---|---|"]
    for c in report["selection"]:
        L.append(f"| {c['case_id']} | {c['group']} | {c['category']} | {c['label']} | "
                 f"{'yes' if not c['matches_known_red_flag_lexicon'] else 'no'} | {c['selection_reason']} |")
    integ = report["integrity"]
    L += ["", "Source corpora (read-only): " + ", ".join(sorted({f"`{c['source_corpus']}` ({c['source_sha256'][:12]})" for c in report["selection"]})) + ".", "",
          "## 3. Frozen code and dataset integrity", "",
          f"* Git commit before the run: `{integ['git_commit_before']}`; working tree clean: {integ['working_tree_clean_before']}.",
          f"* {integ['files_hashed']} files (evaluation framework, production prompt path, RAG, Gemini client, config, schemas, "
          f"fraud rules, frozen V3, approval workflow, datasets, selection) unchanged after the run: **{integ['files_unchanged_after_run']}**"
          + (f" — changed: {integ['changed_files']}" if integ["changed_files"] else "") + ".",
          f"* Production default model (no override): `{integ['production_default_model']}`; evaluation model (process-only override): "
          f"`{integ['evaluation_model']}`.", "",
          "## 4. API usage and quota", "",
          f"| Stage | Used | Approved budget |", "|---|---:|---:|",
          f"| Generation | {api['cumulative_calls'].get('generation', 0)} | {api['budget']['generation']} |",
          f"| Embedding | {api['cumulative_calls'].get('embedding', 0)} | {api['budget']['embedding']} |", "",
          "Each counted call is exactly one HTTP request (no automatic retries); 6 s pacing; free-tier quota "
          "(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 20 per day for this model).", "",
          "## 5. Model reliability and latency", "",
          "| Sample | Model | Generation succeeded | Timeouts | Server errors | Mean latency | p95 latency |", "|---|---|---:|---:|---:|---:|---:|"]
    pilots = report.get("pilots")
    if pilots:
        for model, d in pilots["models"].items():
            g = d["generation"]
            ok = sum(g[c]["succeeded"] for c in ("gemini_no_rag", "gemini_rag"))
            att = sum(g[c]["attempted"] for c in ("gemini_no_rag", "gemini_rag"))
            to = sum(g[c]["timeouts"] for c in ("gemini_no_rag", "gemini_rag"))
            se = sum(g[c]["other_failures"].get("SERVER_ERROR", 0) for c in ("gemini_no_rag", "gemini_rag"))
            a = d["all_success_latency"]
            L.append(f"| Earlier 3-case pilot (V3T-071/131/201) | {model} | {ok}/{att} | {to} | {se} | {a['mean']} s | {a['p95_nearest_rank']} s |")
    if lat["mean"] is not None:
        L.append(f"| **This evaluation (10 new groups)** | {integ['evaluation_model']} | {rel['generation_succeeded']}/{rel['generation_attempted']} | "
                 f"{rel['timeouts']} | {rel['server_errors']} | {lat['mean']:.1f} s | {lat['p95_nearest_rank']:.1f} s |")
    L += ["", f"This evaluation: median {lat['median']:.1f} s, max {lat['max']:.1f} s over {lat['n']} successful responses; "
          f"embedding requests {rel['embedding_latency_s']} s. The earlier pilots used different cases and are reported separately; "
          "they are not pooled." if lat["mean"] is not None else "", "",
          "## 6. Case-by-case predictions", "",
          "| Case | Label | Fallback | Gemini no-docs | Gemini + RAG | V3 | Combined | Combined workflow state | RAG latency |",
          "|---|---|---|---|---|---|---|---|---:|"]
    for p in report["per_case"]:
        L.append(f"| {p['case_id']} | {p['label']} | {p['heuristics_lexical_decision']} | {p['gemini_no_rag_decision']} | "
                 f"{p['gemini_rag_decision']} | {p['v3_decision']} | {p['hybrid_decision']} | {p['hybrid_workflow_state'] or '—'} | "
                 f"{p['gemini_rag_latency_s'] or '—'} s |")
    L += ["", "### Explanations and evidence", ""]
    for p in report["per_case"]:
        L += [f"**{p['case_id']}** ({p['label']}, {p['group']})", "",
              f"* Retrieved evidence (embedding score): " + (", ".join(f"{r['title']} ({r['score']})" for r in p["retrieved"]) or "none"),
              f"* Gemini + RAG — risk {p['gemini_rag_risk']}: {p['gemini_rag_summary'] or '—'}",
              f"  * Red flags: {p['gemini_rag_red_flags'] or '—'}; missing: {p['gemini_rag_missing'] or '—'}",
              f"* Gemini without documents: {p['gemini_no_rag_summary'] or '—'}",
              f"* V3 findings: {p['v3_finding_codes'] or '—'}; V3 reasons: {(p['v3_reasons'] or ['—'])[:2]}",
              f"* Combined: escalated by Gemini: {p['escalated_by_gemini']}; API errors: {p['api_errors'] or 'none'}", ""]
    L += ["## 7. Confusion matrices and outcome counts", "",
          "Detection = FLAG_FOR_REVIEW or REJECTED. NEEDS_MORE_INFORMATION and approval held pending confirmation are not detections. "
          "Negatives = 4 legitimate + 2 borderline.", "",
          "| System | TP | FP | FN | TN | Precision | Recall | F1 | FPR |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in SYSTEMS:
        x = m[s]
        L.append(f"| {TITLES[s]} | {x['tp']} | {x['fp']} | {x['fn']} | {x['tn']} | {pct(x['precision'])}{ci(x['precision_ci'])} | "
                 f"{pct(x['recall'])}{ci(x['recall_ci'])} | {pct(x['f1'])} | {pct(x['fpr'])}{ci(x['fpr_ci'])} |")
    L += ["", "| Outcome | " + " | ".join(TITLES[s] for s in SYSTEMS) + " |", "|---|" + "---:|" * len(SYSTEMS)]
    outcome_rows = [
        ("Fraud-specific review flags (fraud → FLAG)", lambda x: x["fraud_review_flags"]),
        ("Rejections (all labels)", lambda x: x["rejections_total"]),
        ("Information requests (legit / fraud / borderline)", lambda x: "/".join(str(x["info_requests"][l]) for l in ("legitimate", "fraudulent", "borderline"))),
        ("Approved → held pending confirmation (legit / fraud / borderline)", lambda x: "/".join(str(x["approved_held_pending"][l]) for l in ("legitimate", "fraudulent", "borderline"))),
        ("Legitimate unnecessarily escalated (FLAG/REJECT)", lambda x: x["legit_escalated"]),
        ("Legitimate sent for more information", lambda x: x["legit_info_requests"]),
        ("Fraud missed: approved then held", lambda x: x["fraud_missed"]["approved_then_held"]),
        ("Fraud missed: information request", lambda x: x["fraud_missed"]["information_request"]),
        ("Not run / runtime or API failure (all labels)", lambda x: x["not_run_or_error_all"]),
    ]
    for title, f in outcome_rows:
        L.append(f"| {title} | " + " | ".join(str(f(m[s])) for s in SYSTEMS) + " |")
    L += ["", "Three-class decision matrices:", ""]
    for s in SYSTEMS:
        L += [f"*{TITLES[s]}*: " + "; ".join(f"{lab}: {dict(v)}" for lab, v in m[s]["matrix"].items())]
    failure_list = ["{} {} {} {}".format(f["case_id"], f["config"], f["stage"], f["category"]) for f in api["failures"]]
    L += ["", "## 8. Error and disagreement analysis", "",
          "API failures: " + (", ".join(failure_list) or "none") + ".", "",
          "| Case | Label | Pair | A | B |", "|---|---|---|---|---|"]
    for d in report["disagreements"]:
        L.append(f"| {d['case_id']} | {d['label']} | {d['pair']} | {d['a']} | {d['b']} |")
    con = report["contribution"]
    L += ["", "Computed answers to the contribution questions:", "",
          f"1. Fraud flagged by Gemini + RAG but not by V3: {con['fraud_flagged_by_gemini_rag_but_not_v3'] or 'none'}; not by the deterministic fallback: {con['fraud_flagged_by_gemini_rag_but_not_fallback'] or 'none'}.",
          f"2. Correct direction with RAG only: {con['rag_vs_no_rag_correct_direction']['rag_only'] or 'none'}; without documents only: {con['rag_vs_no_rag_correct_direction']['no_rag_only'] or 'none'}; both: {len(con['rag_vs_no_rag_correct_direction']['both'])} cases.",
          f"3. Legitimate cases flagged by Gemini + RAG: {con['legit_flagged_by_gemini_rag'] or 'none'}.",
          f"4. Internally consistent fabricated fraud: {con['consistent_fabrication_case']}.",
          f"5. Unsafe approvals (fraud or borderline APPROVED): " + "; ".join(f"{TITLES[s]} {v or 'none'}" for s, v in con["unsafe_approvals_fraud_or_borderline"].items())
          + ". Manual reviews: " + "; ".join(f"{TITLES[s]} {v}" for s, v in con["manual_reviews"].items()) + ".",
          f"6. Latency: mean {lat['mean']:.1f} s, p95 {lat['p95_nearest_rank']:.1f} s per Gemini verification." if lat["mean"] is not None else "6. Latency: n/a.", "",
          "## 9. Evidence-retrieval analysis", "",
          "| Case | Docs retrieved (embedding score) | Lexical retrieves same documents |", "|---|---|---|"]
    for p in report["per_case"]:
        same = set(r["title"] for r in p["retrieved"]) == set(p["lexical_titles"]) if p["retrieved"] else "—"
        L.append(f"| {p['case_id']} | " + (", ".join(f"{r['title']} ({r['score']})" for r in p["retrieved"]) or "—") + f" | {same} |")
    L += ["", "Every case has one or two short documents, so any retriever returns all of them. Successful retrieval here shows the "
          "pipeline works; it is **not** evidence of relevance ranking quality, which needs gold evidence annotations (protocol v4).", "",
          "## 10. Limitations and statistical uncertainty", "",
          "* 10 cases, one per scenario group: 4 fraud, 4 legitimate, 2 borderline. Wilson intervals above are wide; a single case moves "
          "recall by 25 points. No difference between systems here is statistically meaningful.",
          "* Previously available synthetic data from earlier development cycles; single author; template-generated groups; the 150-case "
          "source was used to motivate V2/V3. This is diagnostic testing, not independent validation.",
          "* Each configuration was run once; Gemini output is non-deterministic (temperature 0.1), so repeat runs could differ.",
          "* Gemini's decisions use the production prompt; red flags attached to an information request are not counted as detections here "
          "(the production router would mark such campaigns FLAGGED).",
          "* Holding a campaign pending confirmation is not fraud detection; whether external confirmation would stop a pending fraud is unmeasured.",
          "", "## 11. Interpretation and recommendation", "", interpretation.strip(), ""]
    return "\n".join(L)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", default="gemini_eval_v1_3_6")
    parser.add_argument("--selection", type=Path, default=Path(__file__).with_name("gemini_eval_v1") / "selection.json")
    parser.add_argument("--pilot-comparison", type=Path, default=RUNS / "gemini_model_comparison_20261116T133718Z" / "results.json")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--interpretation", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    report = build(RUNS / args.experiment, args.selection, args.pilot_comparison, args.freeze)
    interpretation = args.interpretation.read_text() if args.interpretation else "_To be written after reviewing the results._"
    target = args.output_dir or RUNS / args.experiment
    (target / "evaluation_results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    with (target / "per_case_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [k for k in report["per_case"][0]]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["per_case"]:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    (target / "REPORT.md").write_text(render(report, interpretation))
    print(target / "REPORT.md")
    return report


if __name__ == "__main__":
    main()
