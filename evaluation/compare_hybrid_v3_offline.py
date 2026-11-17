"""Offline before/after comparison for hybrid v3.  NO API CALL.  Development evidence only.

  Part 1  the 8 date-aware scenarios (DA-01..08, rendered for 2026-11-17 in the live run):
          frozen V3, frozen hybrid v2 and hybrid v3 under scripted Gemini outputs (failed / approves / information
          request with an ungrounded warning / ungrounded FLAG) plus the one real Gemini answer (DA-02).
  Part 2  the 10 historical cases (saved production-prompt outputs, runs/gemini_eval_v1_3_6): hybrid v2 vs v3.
  Part 3  the frozen benchmark sets (300 / 200 / 150 / 100 cases) with Gemini assumed to approve cleanly - the
          most permissive Gemini output - so every difference comes from the deterministic layers alone.

All three parts are in-sample development data: the DA cases motivated these changes, and the benchmark sets were
used to develop V2/V3.  Nothing here is independent evidence.  Writes runs/hybrid_v3_offline_<timestamp>/.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_evaluation_framework as fw  # noqa: E402
import run_date_aware_dev_eval as ev  # noqa: E402
from app.services.development_gemini_verification import assess_dates as v2_assess_dates  # noqa: E402
from app.services.development_gemini_verification import combine as v2_combine  # noqa: E402
from app.services.development_hybrid_v3 import POLICY_VERSION, combine as v3_combine, v3_case  # noqa: E402
from app.services.development_hybrid_v3.config import digest  # noqa: E402
from app.services.development_verifier_v3 import verify_case  # noqa: E402
from app.services.development_verifier_v3.config import DEFAULT_CONFIG  # noqa: E402
from app.services.development_verifier_v3.normalize import find_dates  # noqa: E402

RUNS = Path(__file__).with_name("runs")
LIVE = RUNS / "date_aware_dev_eval_live"
DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}
APPROVE = {"status": "OK", "decision": "APPROVED", "concerns": [], "red_flag_texts": [], "missing_requirements": []}
SCENARIOS = {
    "gemini_failed": {"status": "FAILED", "failure_category": "SERVER_ERROR"},
    "gemini_approves": APPROVE,
    "gemini_info_request_ungrounded_warning": {
        "status": "OK", "decision": "NEEDS_MORE_INFORMATION", "red_flag_texts": [], "missing_requirements": [],
        "concerns": [{"category": "SUSPECTED_FRAUD", "description": "The supporting paperwork could be forged.",
                      "evidence_quote": ""}]},
    "gemini_flags_ungrounded": {
        "status": "OK", "decision": "FLAG_FOR_REVIEW", "red_flag_texts": [], "missing_requirements": [],
        "concerns": [{"category": "SUSPECTED_FRAUD", "description": "This campaign is a scam.", "evidence_quote": ""}]},
}
BENCHMARKS = {"final_test_300": "final_test_scenarios_v3.jsonl", "fundraising_200": "fundraising_scenarios.jsonl",
              "independent_test_150": "independent_test_150.jsonl", "independent_benchmark_100": "independent_benchmark_100.jsonl"}


def _campaign_text(data):
    return " ".join(str(data.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state"))


def run_v2(data, v3, gemini, chunks, reference):
    dates = v2_assess_dates([(d["title"], d.get("content", "")) for d in data.get("documents", [])], reference)
    out = v2_combine(v3.decision.value, gemini, chunks, _campaign_text(data), dates, category=data["category"],
                     beneficiary_type=data.get("beneficiary_type"), v3_information_requests=v3.information_requests)
    return out.decision, out.triggers[0]


def run_v3(data, v3, gemini, chunks, reference):
    out = v3_combine(data, v3, gemini, chunks, reference)
    return out


def part_da():
    cases = ev.load_run_cases(LIVE)
    live = {json.loads(l)["case_id"]: json.loads(l)["record"] for l in (LIVE / "outputs.jsonl").read_text().splitlines() if l.strip()}
    rows = []
    for case in cases:
        data, reference = case["input"], date.fromisoformat(case["input"]["submitted_on"])
        chunks = ev.evidence(case)
        v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
        scenarios = dict(SCENARIOS)
        if case["case_id"] in live:
            scenarios["live_gemini_answer"] = {"status": "OK", **live[case["case_id"]]}
        row = {"case_id": case["case_id"], "label": case["ground_truth"], "scenario_type": case["scenario_type"],
               "v3_before": v3.decision.value, "by_gemini_output": {}}
        for name, gemini in scenarios.items():
            before = run_v2(data, v3, gemini, chunks, reference)
            after = run_v3(data, v3, gemini, chunks, reference)
            row["by_gemini_output"][name] = {"hybrid_v2": f"{before[0]} ({before[1]})",
                                             "hybrid_v3": f"{after.decision} ({after.triggers[0]})",
                                             "hybrid_v3_review_basis": after.review_basis}
        detail = run_v3(data, v3, APPROVE, chunks, reference)
        row.update({"v3_effective_after": detail.v3_effective_decision, "refuted_v3_findings": detail.refuted_v3_findings,
                    "cross_document_findings": detail.cross_document_findings,
                    "financial_evidence": {k: detail.financial_evidence[k] for k in ("status", "goal", "documented_need")},
                    "required_confirmations": detail.required_confirmations})
        rows.append(row)
    return rows


def part_historical():
    directory = RUNS / "gemini_eval_v1_3_6"
    cache = [json.loads(l) for l in (directory / "cache.jsonl").read_text().splitlines() if l.strip()]
    results = {(r["config"], r["case_id"]): r for r in cache if r.get("stage") == "result"}
    retrieval = {r["case_id"]: r for r in cache if r.get("stage") == "retrieval"}
    run_date = min(datetime.fromisoformat(r["cached_at"]).date() for r in cache)
    rows = []
    for line in (Path(__file__).with_name("gemini_eval_v1") / "cases.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        data, cid = case["input"], case["case_id"]
        record = results.get(("gemini_rag", cid))
        gemini = None if record is None else {"status": "OK", "decision": record["decision"],
                                              "red_flag_texts": record.get("red_flag_texts") or [],
                                              "missing_requirements": record.get("missing_requirements") or []}
        reference = date.fromisoformat(data["submitted_on"]) if data.get("submitted_on") else run_date
        chunks = (retrieval.get(cid) or {}).get("chunks", [])
        v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
        before = run_v2(data, v3, gemini, chunks, reference)
        after = run_v3(data, v3, gemini, chunks, reference)
        rows.append({"case_id": cid, "label": case["ground_truth"], "v3": v3.decision.value,
                     "hybrid_v2": before[0], "hybrid_v2_trigger": before[1], "hybrid_v3": after.decision,
                     "hybrid_v3_trigger": after.triggers[0], "hybrid_v3_review_basis": after.review_basis,
                     "financial": after.financial_evidence["status"],
                     "cross_document": [f["code"] for f in after.cross_document_findings]})
    return rows


def _reference(data):
    if data.get("submitted_on"):
        return date.fromisoformat(data["submitted_on"]), "submitted_on"
    found = [value for d in data.get("documents", []) for value, *_ in find_dates(d.get("content", ""))]
    if found:
        return max(found), "latest_document_date"
    return datetime.now(ev.IST).date(), "today_asia_kolkata"


def part_benchmarks():
    out = {}
    for name, filename in BENCHMARKS.items():
        cases = [json.loads(l) for l in (Path(__file__).with_name(filename)).read_text().splitlines() if l.strip()]
        transitions = defaultdict(Counter)
        decisions = defaultdict(lambda: defaultdict(Counter))
        cross_codes, financial_status, refutations, reference_basis = Counter(), defaultdict(Counter), Counter(), Counter()
        changed = []
        for case in cases:
            data, label = case["input"], case["ground_truth"]
            reference, basis = _reference(data)
            reference_basis[basis] += 1
            v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
            v2 = run_v2(data, v3, APPROVE, [], reference)[0]
            after = run_v3(data, v3, APPROVE, [], reference)
            for system, decision in (("v3_alone", v3.decision.value), ("hybrid_v2", v2), ("hybrid_v3", after.decision)):
                decisions[system][label][decision] += 1
            transitions[label][f"{v2} -> {after.decision}"] += 1
            for f in after.cross_document_findings:
                cross_codes[(f["code"], label)] += 1
            financial_status[label][after.financial_evidence["status"]] += 1
            refutations[label] += bool(after.refuted_v3_findings)
            if v2 != after.decision:
                changed.append({"case_id": case["case_id"], "label": label, "hybrid_v2": v2, "hybrid_v3": after.decision,
                                "trigger": after.triggers[0]})
        out[name] = {"cases": len(cases), "reference_date_basis": dict(reference_basis),
                     "decisions": {s: {l: dict(c) for l, c in v.items()} for s, v in decisions.items()},
                     "transitions_hybrid_v2_to_v3": {l: dict(c) for l, c in transitions.items()},
                     "cross_document_findings": {f"{code}|{label}": n for (code, label), n in sorted(cross_codes.items())},
                     "financial_evidence_status": {l: dict(c) for l, c in financial_status.items()},
                     "v3_future_date_findings_refuted": dict(refutations), "changed_cases": changed}
    return out


def summarise(benchmarks):
    rows = []
    for name, data in benchmarks.items():
        for system in ("v3_alone", "hybrid_v2", "hybrid_v3"):
            d = data["decisions"][system]
            get = lambda label, decisions: sum(d.get(label, {}).get(x, 0) for x in decisions)  # noqa: E731
            rows.append({"dataset": name, "system": system,
                         "fraud_detected": get("fraudulent", DETECT), "fraud_total": sum(d.get("fraudulent", {}).values()),
                         "fraud_approved": get("fraudulent", {"APPROVED"}),
                         "legit_escalated": get("legitimate", DETECT), "legit_total": sum(d.get("legitimate", {}).values()),
                         "legit_approved": get("legitimate", {"APPROVED"}),
                         "information_requests": sum(get(l, {"NEEDS_MORE_INFORMATION"}) for l in d),
                         "manual_reviews": sum(get(l, DETECT) for l in d)})
    return rows


def render(report):
    L = ["# Hybrid v3 offline before/after (no API call, development evidence only)", "",
         f"Policy `{report['policy_version']}` (settings digest `{report['settings_digest']}`), created "
         f"{report['created_utc']}. {report['classification']}", "",
         "## Part 1 - DA scenarios: decision by Gemini output (hybrid v2 -> hybrid v3)", "",
         "| Case | Label | V3 | Gemini output | Hybrid v2 | Hybrid v3 | Review basis |", "|---|---|---|---|---|---|---|"]
    for r in report["da_scenarios"]:
        for name, x in r["by_gemini_output"].items():
            L.append(f"| {r['case_id']} | {r['label']} | {r['v3_before']} | {name} | {x['hybrid_v2']} | {x['hybrid_v3']} | "
                     f"{x['hybrid_v3_review_basis'] or ''} |")
    L += ["", "## Part 2 - 10 historical cases (saved production-prompt outputs; in-sample)", "",
          "| Case | Label | V3 | Hybrid v2 | Hybrid v3 | v3 trigger | Financial evidence |", "|---|---|---|---|---|---|---|"]
    for r in report["historical_10"]:
        L.append(f"| {r['case_id']} | {r['label']} | {r['v3']} | {r['hybrid_v2']} | {r['hybrid_v3']} | {r['hybrid_v3_trigger']} | "
                 f"{r['financial']} |")
    L += ["", "## Part 3 - frozen benchmark sets, Gemini assumed to approve cleanly (deterministic layers only)", "",
          "| Dataset | System | Fraud detected | Fraud approved | Legit escalated | Legit approved | Info requests | Manual reviews |",
          "|---|---|---|---|---|---|---|---|"]
    for s in report["benchmark_summary"]:
        L.append(f"| {s['dataset']} | {s['system']} | {s['fraud_detected']}/{s['fraud_total']} | {s['fraud_approved']} | "
                 f"{s['legit_escalated']}/{s['legit_total']} | {s['legit_approved']}/{s['legit_total']} | "
                 f"{s['information_requests']} | {s['manual_reviews']} |")
    for name, data in report["benchmarks"].items():
        L += ["", f"### {name}: reference date basis {data['reference_date_basis']}", "",
              f"* hybrid v2 -> v3 transitions: {data['transitions_hybrid_v2_to_v3']}",
              f"* cross-document findings (code|label): {data['cross_document_findings'] or 'none'}",
              f"* financial evidence status by label: {data['financial_evidence_status']}",
              f"* V3 future-date findings refuted, by label: {data['v3_future_date_findings_refuted']}"]
    return "\n".join(L) + "\n"


def main():
    benchmarks = part_benchmarks()
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "policy_version": POLICY_VERSION,
              "settings_digest": digest(),
              "classification": "DEVELOPMENT, IN-SAMPLE: the DA cases motivated these changes and the benchmark sets were "
                                "used to develop V2/V3. No API call was made; Gemini outputs are scripted or saved.",
              "da_scenarios": part_da(), "historical_10": part_historical(), "benchmarks": benchmarks,
              "benchmark_summary": summarise(benchmarks)}
    target = RUNS / f"hybrid_v3_offline_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    target.mkdir(parents=True, exist_ok=False)
    (target / "results.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    (target / "report.md").write_text(render(report), encoding="utf-8")
    print(target)
    return report


if __name__ == "__main__":
    main()
