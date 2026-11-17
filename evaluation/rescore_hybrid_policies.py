"""DEVELOPMENT (IN-SAMPLE) re-scoring of saved Gemini outputs under three decision policies.  No API call.

Systems compared on the identical saved outputs of runs/gemini_eval_v1_3_6 (10 cases, production prompt):
  original_v3        frozen V3 alone
  existing_hybrid    frozen V3 + Gemini, frozen v1 rule: escalate on Gemini's decision OR any red flag
                     (deployed semantics: a missing Gemini result is a VERIFICATION_ERROR, never an approval)
  improved_hybrid    frozen V3 + Gemini, hybrid-v2 policy (app/services/development_gemini_verification):
                     generic warnings stay information requests; only explicit Gemini warnings, grounded
                     contradictions and deterministic date problems escalate

The improved policy was written AFTER inspecting these outputs, so this comparison is in-sample development
evidence, not evidence of improvement.  It also cannot exercise the dated prompt (the saved outputs were produced
by the production prompt); only the policy and the deterministic date check are applied.
"""
import argparse
import csv
import json
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.development_gemini_verification import POLICY_VERSION, assess_dates, combine
from app.services.development_gemini_verification.config import digest as policy_digest
from app.services.development_verifier_v3 import verify_case
from evaluate_development_verifier_v3 import v3_input
from group_uncertainty import wilson

RUNS = Path(__file__).with_name("runs")
SYSTEMS = ["original_v3", "existing_hybrid", "improved_hybrid"]
DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}


def existing_rule(v3: str, gemini_rag: dict) -> str:
    """Frozen v1 hybrid rule (evaluation/gemini_evaluation_framework.py::hybrid_decision)."""
    if v3 in ("FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR"):
        return v3
    if gemini_rag is None:
        return "VERIFICATION_ERROR"
    return "FLAG_FOR_REVIEW" if gemini_rag["flagged"] else v3


def metrics(rows, system):
    fraud = [r for r in rows if r["label"] == "fraudulent"]
    neg = [r for r in rows if r["label"] != "fraudulent"]
    legit = [r for r in rows if r["label"] == "legitimate"]
    d = lambda r: r[system]
    tp, fp = sum(d(r) in DETECT for r in fraud), sum(d(r) in DETECT for r in neg)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / len(fraud)
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
    return {"tp": tp, "fp": fp, "fn": len(fraud) - tp, "tn": len(neg) - fp,
            "precision": precision, "precision_ci": wilson(tp, tp + fp), "recall": recall, "recall_ci": wilson(tp, len(fraud)),
            "f1": f1, "fpr": fp / len(neg), "fpr_ci": wilson(fp, len(neg)),
            "legit_escalated": sum(d(r) in DETECT for r in legit),
            "unsafe_approvals": [r["case_id"] for r in rows if r["label"] != "legitimate" and d(r) == "APPROVED"],
            "manual_reviews": sum(d(r) == "FLAG_FOR_REVIEW" for r in rows),
            "rejections": sum(d(r) == "REJECTED" for r in rows),
            "information_requests": sum(d(r) == "NEEDS_MORE_INFORMATION" for r in rows),
            "verification_errors": sum(d(r) == "VERIFICATION_ERROR" for r in rows),
            "approved_held_pending": sum(d(r) == "APPROVED" for r in rows)}


def run(experiment: str):
    directory = RUNS / experiment
    cache = [json.loads(l) for l in (directory / "cache.jsonl").read_text().splitlines() if l.strip()]
    results = {(r["config"], r["case_id"]): r for r in cache if r.get("stage") == "result"}
    retrieval = {r["case_id"]: r for r in cache if r.get("stage") == "retrieval"}
    cases = {json.loads(l)["case_id"]: json.loads(l) for l in
             (Path(__file__).with_name("gemini_eval_v1") / "cases.jsonl").read_text().splitlines() if l.strip()}
    run_date = min(datetime.fromisoformat(r["cached_at"]).date() for r in cache)
    rows, consistency = [], {}
    for cid, case in cases.items():
        data = case["input"]
        v3 = verify_case(v3_input(data))
        gemini_record = results.get(("gemini_rag", cid))
        gemini = None if gemini_record is None else {
            "status": "OK", "decision": gemini_record["decision"], "red_flag_texts": gemini_record.get("red_flag_texts") or [],
            "missing_requirements": gemini_record.get("missing_requirements") or []}
        submitted = date.fromisoformat(data["submitted_on"]) if data.get("submitted_on") else None
        reference = submitted or run_date
        dates = assess_dates([(d["title"], d["content"]) for d in data.get("documents", [])], reference)
        campaign_text = " ".join(str(data.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state"))
        improved = combine(v3.decision.value, gemini, (retrieval.get(cid) or {}).get("chunks", []), campaign_text, dates,
                           category=data["category"], beneficiary_type=data.get("beneficiary_type"),
                           v3_information_requests=v3.information_requests)
        existing = existing_rule(v3.decision.value, gemini_record)
        if ("hybrid", cid) in results:
            consistency[cid] = results[("hybrid", cid)]["decision"] == existing
        rows.append({"case_id": cid, "label": case["ground_truth"], "group": case["scenario_family"],
                     "category": data["category"], "reference_date": reference.isoformat(),
                     "gemini_rag": gemini_record["decision"] if gemini_record else "NOT_RUN (HTTP 503)",
                     "gemini_red_flags": len((gemini or {}).get("red_flag_texts") or []),
                     "original_v3": v3.decision.value, "existing_hybrid": existing, "improved_hybrid": improved.decision,
                     "improved_workflow_state": improved.workflow_state, "improved_triggers": improved.triggers,
                     "improved_reason": improved.reasons[0], "unverified_concerns": improved.unverified_concerns,
                     "vetoed_concerns": improved.vetoed_concerns,
                     "document_dates": [f"{d.document}: {d.raw} {d.kind} {d.status}" for d in dates.dates]})
    generation = [r for (c, _), r in results.items() if c in ("gemini_rag", "gemini_no_rag")]
    failures = [json.loads(l) for l in (directory / "failures.jsonl").read_text().splitlines() if l.strip()]
    latencies = sorted(r["generation_latency_ms"] / 1000 for r in generation)
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(), "experiment": experiment,
        "classification": "DEVELOPMENT, IN-SAMPLE: the improved policy was designed after inspecting these saved outputs.",
        "policy_version": POLICY_VERSION, "policy_digest": policy_digest(), "reference_date_rule":
            "case submitted_on if present, else the evaluation run date " + run_date.isoformat(),
        "existing_rule_reproduces_recorded_decisions": consistency,
        "rows": rows, "metrics": {s: metrics(rows, s) for s in SYSTEMS},
        "api": {"generation_attempted": len(generation) + len([f for f in failures if f["stage"] == "generation"]),
                "generation_succeeded": len(generation), "failures": [f["category"] for f in failures],
                "latency_s": {"mean": statistics.mean(latencies), "median": statistics.median(latencies),
                              "p95_nearest_rank": latencies[max(0, -(-95 * len(latencies) // 100) - 1)]},
                "note": "Both hybrids consume the same Gemini outputs; the improved policy adds no API calls or latency."},
    }


def pct(v):
    return "n/a" if v is None else f"{100 * v:.0f}%"


def ci(v):
    return "" if not v else f" ({100 * v[0]:.0f}–{100 * v[1]:.0f}%)"


def render(report) -> str:
    m = report["metrics"]
    title = {"original_v3": "Original V3", "existing_hybrid": "Existing V3 + Gemini", "improved_hybrid": "Improved V3 + Gemini"}
    L = ["# Development re-scoring: original V3 vs existing vs improved V3 + Gemini", "",
         f"> **{report['classification']}** It is not evidence of improvement and not an independent test. "
         f"Policy `{report['policy_version']}` (digest `{report['policy_digest']}`). Saved outputs of `{report['experiment']}` "
         "(production prompt; the dated prompt is not exercised). No API call was made.", "",
         f"Existing rule reproduces every recorded combined decision: **{all(report['existing_rule_reproduces_recorded_decisions'].values())}** "
         f"({len(report['existing_rule_reproduces_recorded_decisions'])} cases). Date reference: {report['reference_date_rule']}.", "",
         "## Fraud detection and false positives (separately)", "",
         "Detection = FLAG_FOR_REVIEW or REJECTED. 4 fraudulent, 6 non-fraud (4 legitimate + 2 borderline).", "",
         "| System | Recall (fraud detected) | False-positive rate | Precision | F1 | TP/FP/FN/TN |", "|---|---:|---:|---:|---:|---|"]
    for s in SYSTEMS:
        x = m[s]
        L.append(f"| {title[s]} | {x['tp']}/4 = {pct(x['recall'])}{ci(x['recall_ci'])} | {x['fp']}/6 = {pct(x['fpr'])}{ci(x['fpr_ci'])} | "
                 f"{pct(x['precision'])}{ci(x['precision_ci'])} | {pct(x['f1'])} | {x['tp']}/{x['fp']}/{x['fn']}/{x['tn']} |")
    L += ["", "## Safety and workload", "", "| System | Unsafe approvals (fraud/borderline approved) | Legitimate escalated | "
          "Manual reviews | Information requests | Verification errors | Approved → pending confirmation |", "|---|---|---:|---:|---:|---:|---:|"]
    for s in SYSTEMS:
        x = m[s]
        L.append(f"| {title[s]} | {len(x['unsafe_approvals'])} {x['unsafe_approvals'] or ''} | {x['legit_escalated']} | {x['manual_reviews']} | "
                 f"{x['information_requests']} | {x['verification_errors']} | {x['approved_held_pending']} |")
    api = report["api"]
    L += ["", "## API reliability and latency (same Gemini outputs for both hybrids)", "",
          f"Generation {api['generation_succeeded']}/{api['generation_attempted']} succeeded; failures: {api['failures']}; latency mean "
          f"{api['latency_s']['mean']:.1f} s, median {api['latency_s']['median']:.1f} s, p95 {api['latency_s']['p95_nearest_rank']:.1f} s. "
          + api["note"], "", "## Per case", "",
          "| Case | Label | Gemini + RAG | Red flags | Original V3 | Existing | Improved | Improved trigger | Change |",
          "|---|---|---|---:|---|---|---|---|---|"]
    for r in report["rows"]:
        good = lambda dec: {"fraudulent": dec in DETECT, "legitimate": dec == "APPROVED",
                            "borderline": dec in ("NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW")}[r["label"]]
        e, i = r["existing_hybrid"], r["improved_hybrid"]
        change = "—" if e == i else ("improvement" if good(i) and not good(e) else "REGRESSION" if good(e) and not good(i)
                                     else "changed")
        L.append(f"| {r['case_id']} | {r['label']} | {r['gemini_rag']} | {r['gemini_red_flags']} | {r['original_v3']} | {e} | {i} | "
                 f"{', '.join(r['improved_triggers'])} | {change} |")
    L += ["", "Vetoed model claims (deterministic date check) and unverified concerns:", ""]
    for r in report["rows"]:
        for v in r["vetoed_concerns"]:
            L.append(f"* {r['case_id']} — vetoed: {v}")
        for u in r["unverified_concerns"]:
            L.append(f"* {r['case_id']} — unverified (not escalated): {u}")
    return "\n".join(L) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", default="gemini_eval_v1_3_6")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    report = run(args.experiment)
    target = args.output_dir or RUNS / f"hybrid_policy_rescoring_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    target.mkdir(parents=True, exist_ok=False)
    (target / "results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    with (target / "per_case.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report["rows"][0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in report["rows"])
    (target / "report.md").write_text(render(report))
    print(target)


if __name__ == "__main__":
    main()
