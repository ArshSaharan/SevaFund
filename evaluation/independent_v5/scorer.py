"""Scoring pipeline for the v5 independent test (standard library only; never imports `app`).

Reads, never writes: the run directory, the adjudicated labels and their seal, the submission and the
pre-registration.  Writes only into a new output directory outside app/.  Every metric, criterion and comparison
is the pre-registered one (evaluation/independent_test_v5/preregistration.json); nothing here is tuned to results.
"""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import config, labels as label_io, stats

ELIGIBLE = "ELIGIBLE_PENDING_CONFIRMATION"
INVALID_OUTPUT = {"EMPTY_CANDIDATES", "TRUNCATED_RESPONSE", "MODEL_BLOCKED", "EMPTY_MODEL_TEXT", "JSON_PARSE_ERROR",
                  "SCHEMA_VALIDATION", "UNKNOWN_RECOMMENDATION", "INVALID_API_JSON", "INVALID_API_RESPONSE"}


# ------------------------------------------------------------------ inputs
def _read_jsonl(path: Path) -> List[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def load_inputs(run_dir: Path, label_file: Path, label_seal: Path, submission: Path,
                prereg_path: Path = config.PREREG_PATH) -> dict:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    problems = []
    if config.sha256_file(submission) != manifest["submission_sha256"]:
        problems.append("the submission differs from the one the run used")
    if config.sha256_file(prereg_path) != manifest["prereg_sha256"]:
        problems.append("the pre-registration differs from the one the run used")
    seal = json.loads(Path(label_seal).read_text(encoding="utf-8"))
    if seal.get("sha256") != config.sha256_file(label_file):
        problems.append("the adjudicated labels differ from their seal")
    if manifest.get("label_seal_sha256") and manifest["label_seal_sha256"] != config.sha256_file(label_seal):
        problems.append("the label seal differs from the one recorded by the live run")
    if problems:
        raise SystemExit("Refusing to score:\n- " + "\n- ".join(problems))
    return {"manifest": manifest, "state": json.loads((run_dir / "state.json").read_text(encoding="utf-8")),
            "outputs": _read_jsonl(run_dir / "outputs.jsonl"), "attempts": _read_jsonl(run_dir / "attempts.jsonl"),
            "requests": _read_jsonl(run_dir / "requests.jsonl"), "labels": label_io.read_final(label_file),
            "label_seal": seal, "cases": {c["case_id"]: c for c in config.read_jsonl(submission)},
            "prereg": json.loads(Path(prereg_path).read_text(encoding="utf-8"))}


def build_rows(inputs: dict) -> Dict[str, List[dict]]:
    """One row per case per system, joining sealed labels with run outputs."""
    missing = sorted(o["case_id"] for o in inputs["outputs"] if o["case_id"] not in inputs["labels"])
    if missing:
        raise SystemExit(f"Refusing to score: cases without adjudicated labels {missing}")
    rows = {s: [] for s in config.SYSTEMS}
    detection = set(inputs["prereg"]["analysis"]["detection"])
    for output in inputs["outputs"]:
        label = inputs["labels"][output["case_id"]]
        case = inputs["cases"][output["case_id"]]
        base = {"case_id": output["case_id"], "group": output["scenario_group"], "category": output["category"],
                "truth": label["truth_label"], "documentation": label["documentation"],
                "stratum": config.stratum(label["truth_label"], label["documentation"]),
                "dossier_detectable": label["detectable_from_dossier"] == "yes",
                "mechanism": case.get("mechanism"), "keyword_free": bool(case.get("keyword_free")),
                "incomplete_subtype": case.get("incomplete_subtype"), "llm_assisted": bool(case.get("llm_assisted")),
                "gemini_valid": output["gemini"]["status"] == "OK",
                "gemini_failure": output["gemini"]["failure_category"],
                "long_dossier": output["retrieval"]["total_chunks"] > 5,
                "all_chunks_retrieved": output["retrieval"]["all_chunks_retrieved"]}
        for system in config.SYSTEMS:
            result = output["systems"][system]
            sim = result["confirmation_simulated"]
            amount = result.get("amount_check_simulated") or {}
            decision = result["decision"]
            rows[system].append({**base, "decision": decision, "detected": decision in detection,
                                 "approved": decision == "APPROVED", "nmi": decision == "NEEDS_MORE_INFORMATION",
                                 "flag": decision == "FLAG_FOR_REVIEW", "error": decision == "VERIFICATION_ERROR",
                                 "rejected": decision == "REJECTED", "triggers": result.get("triggers") or [],
                                 "review_basis": result.get("review_basis"), "workflow_state": result["workflow_state"],
                                 "initial_state": sim["initial_state"], "activated": sim["activated"],
                                 "activation_allowed": sim["activation_allowed"], "pending_checks": sim["pending_checks"],
                                 "satisfied": sim["satisfied"], "confirmation_records": sim["confirmation_records"],
                                 "campaign_supplied_satisfied": sim["campaign_supplied_satisfied"],
                                 "activation_triggers": sim["activation_triggers"],
                                 "amount_outcome": amount.get("outcome")})
    return rows


# ------------------------------------------------------------------ estimators
class Estimator:
    def __init__(self, prereg: dict):
        a = prereg["analysis"]
        self.reps, self.seed = a["bootstrap_replications"], a["bootstrap_seed"]

    def rate(self, rows: List[dict], numerator: Callable[[dict], bool], denominator: Callable[[dict], bool]) -> dict:
        den = [r for r in rows if denominator(r)]
        groups = defaultdict(list)
        for r in den:
            groups[r["group"]].append(int(bool(numerator(r))))
        primary = stats.clustered_proportion(dict(groups))
        primary["bootstrap_ci"] = stats.ratio_bootstrap([(sum(v), len(v)) for v in groups.values()], self.reps, self.seed)
        primary["group_level"] = self._group_level(groups)
        return primary

    @staticmethod
    def _group_level(groups: dict) -> dict:
        votes = [int(sum(v) * 2 > len(v)) for v in groups.values() if v]
        return {"groups": len(votes), "majority_rate": round(sum(votes) / len(votes), 4) if votes else None,
                "ci": stats.wilson(sum(votes), len(votes))}

    def ratio(self, rows: List[dict], numerator: Callable[[dict], bool], denominator: Callable[[dict], bool]) -> dict:
        """Ratios whose denominator is itself an outcome (precision)."""
        groups = defaultdict(lambda: [0, 0])
        for r in rows:
            if denominator(r):
                groups[r["group"]][1] += 1
                groups[r["group"]][0] += int(bool(numerator(r)))
        num, den = sum(v[0] for v in groups.values()), sum(v[1] for v in groups.values())
        boot = stats.ratio_bootstrap([tuple(v) for v in groups.values()], self.reps, self.seed)
        return {"n": den, "successes": num, "estimate": round(num / den, 4) if den else None,
                "ci": boot, "interval_method": "cluster bootstrap (precision has an outcome-defined denominator)"}

    @staticmethod
    def count(rows: List[dict], predicate: Callable[[dict], bool], population: Callable[[dict], bool]) -> dict:
        pop = [r for r in rows if population(r)]
        events = [r["case_id"] for r in pop if predicate(r)]
        groups = len({r["group"] for r in pop})
        return {"count": len(events), "cases": events, "population_cases": len(pop), "population_groups": groups,
                "upper_95_if_zero_case_level": stats.wilson(0, len(pop))[1] if pop and not events else None,
                "upper_95_if_zero_group_level": stats.wilson(0, groups)[1] if groups and not events else None}


F = lambda r: r["stratum"] == "F"
L = lambda r: r["stratum"] == "L"
I = lambda r: r["stratum"] == "I"
B = lambda r: r["stratum"] == "B"
LEGIT = lambda r: r["stratum"] in ("L", "I")
INCOMPLETE = lambda r: r["documentation"] == "incomplete"
ALL = lambda r: True


def _unsafe_activation(r: dict) -> Dict[str, bool]:
    independent = {"OFFICIAL_REGISTRY", "OFFICIAL_DIRECTORY", "PLATFORM_KYC", "PRIOR_VERIFIED_RECORD"}
    if not r["activated"]:
        return {"b": False, "c": False, "d": False, "e": False}
    return {"b": (not r["activation_allowed"]) or bool(r["pending_checks"]) or
                 any(s["source"] not in independent or s["outcome"] != "CONFIRMED" for s in r["satisfied"]),
            "c": r["documentation"] == "incomplete",
            "d": r["confirmation_records"] == 0 or any(t != "confirmation" for t in r["activation_triggers"]),
            "e": r["campaign_supplied_satisfied"] > 0}


def system_metrics(rows: List[dict], est: Estimator) -> dict:
    m = {
        "M1_fraud_recall": est.rate(rows, lambda r: r["detected"], F),
        "M1a_dossier_detectable_fraud_recall": est.rate(rows, lambda r: r["detected"], lambda r: F(r) and r["dossier_detectable"]),
        "M1b_fraud_held_before_activation_simulated": est.rate(rows, lambda r: not r["activated"], F),
        "M2_false_positive_rate": est.rate(rows, lambda r: r["detected"], LEGIT),
        "M3_fraud_precision": est.ratio(rows, F, lambda r: r["detected"] and (F(r) or LEGIT(r))),
        "M3s_fraud_precision_borderline_as_negative": est.ratio(rows, F, lambda r: r["detected"]),
        "M4_legitimate_approval_rate": est.rate(rows, lambda r: r["approved"], L),
        "M4b_legitimate_approval_rate_all": est.rate(rows, lambda r: r["approved"], LEGIT),
        "M4c_legitimate_activation_rate_simulated": est.rate(rows, lambda r: r["activated"], L),
        "M5_information_request_rate": est.rate(rows, lambda r: r["nmi"], ALL),
        "M5L_avoidable_information_requests": est.rate(rows, lambda r: r["nmi"], L),
        "M5I_appropriate_information_requests": est.rate(rows, lambda r: r["nmi"], I),
        "M6_manual_review_rate": est.rate(rows, lambda r: r["flag"], ALL),
        "M6nf_non_fraud_manual_review_rate": est.rate(rows, lambda r: r["flag"], lambda r: not F(r)),
        "M6_review_basis": dict(Counter(r["review_basis"] or "NONE" for r in rows if r["flag"])),
        "M7I_unsafe_provisional_approvals_incomplete": est.count(rows, lambda r: r["approved"], INCOMPLETE),
        "M7F_unsafe_provisional_approvals_fraud": est.rate(rows, lambda r: r["approved"], F),
        "M7Fd_unsafe_provisional_approvals_dossier_detectable_fraud": est.rate(
            rows, lambda r: r["approved"], lambda r: F(r) and r["dossier_detectable"]),
        "M7B_unsafe_provisional_approvals_borderline": est.rate(rows, lambda r: r["approved"], B),
        "M8a_fraud_activations_simulated": est.rate(rows, lambda r: r["activated"], F),
        "M8b_activations_with_unconfirmed_check": est.count(rows, lambda r: _unsafe_activation(r)["b"], ALL),
        "M8c_activations_of_incomplete_cases": est.count(rows, lambda r: _unsafe_activation(r)["c"], ALL),
        "M8d_activations_without_confirmation_record": est.count(rows, lambda r: _unsafe_activation(r)["d"], ALL),
        "M8e_activations_via_campaign_supplied_contact": est.count(rows, lambda r: _unsafe_activation(r)["e"], ALL),
        "M9a_fraud_passing_confirmation_simulated": est.rate(rows, lambda r: r["activated"],
                                                             lambda r: F(r) and r["initial_state"] == ELIGIBLE),
        "M9b_legitimate_blocked_at_confirmation_simulated": est.rate(rows, lambda r: not r["activated"],
                                                                     lambda r: LEGIT(r) and r["initial_state"] == ELIGIBLE),
        "M9c_campaign_supplied_contacts_accepted": est.count(rows, lambda r: r["campaign_supplied_satisfied"] > 0, ALL),
        "M9d_amount_check_simulated": {
            "amount_inflation_fraud_contradicted": est.rate(rows, lambda r: r["amount_outcome"] == "CONTRADICTED",
                                                            lambda r: F(r) and r["mechanism"] == "amount_inflation" and r["activated"]),
            "fraud_contradicted": est.rate(rows, lambda r: r["amount_outcome"] == "CONTRADICTED", lambda r: F(r) and r["activated"]),
            "legitimate_contradicted": est.rate(rows, lambda r: r["amount_outcome"] == "CONTRADICTED", lambda r: LEGIT(r) and r["activated"]),
            "open_undisclosed": est.rate(rows, lambda r: r["amount_outcome"] == "OPEN", lambda r: r["activated"])},
        "G3_rejections_from_gemini_alone": est.count(
            rows, lambda r: r["rejected"] and r["triggers"] and all(str(t).upper().startswith("GEMINI") for t in r["triggers"]), ALL),
        "G4_provisional_approval_treated_as_activation": est.count(
            rows, lambda r: r["approved"] and (r["workflow_state"] != ELIGIBLE or r["initial_state"] != ELIGIBLE), ALL),
        "decisions": {s: dict(Counter(r["decision"] for r in rows if r["stratum"] == s)) for s in "LIFB"},
    }
    return m


def subgroup_tables(rows: List[dict], est: Estimator) -> dict:
    out = {"by_category": {}, "by_mechanism": {}, "by_incomplete_subtype": {}, "by_keyword_free": {},
           "by_llm_assisted": {}, "by_long_dossier": {}}
    for category in sorted({r["category"] for r in rows}):
        sub = [r for r in rows if r["category"] == category]
        out["by_category"][category] = {"fraud_recall": est.rate(sub, lambda r: r["detected"], F)["estimate"],
                                        "false_positive_rate": est.rate(sub, lambda r: r["detected"], LEGIT)["estimate"],
                                        "legitimate_approval": est.rate(sub, lambda r: r["approved"], L)["estimate"]}
    for mechanism in sorted({r["mechanism"] for r in rows if F(r) and r["mechanism"]}):
        sub = [r for r in rows if F(r) and r["mechanism"] == mechanism]
        out["by_mechanism"][mechanism] = {"cases": len(sub), "detected": sum(r["detected"] for r in sub),
                                          "provisionally_approved": sum(r["approved"] for r in sub),
                                          "activated_simulated": sum(r["activated"] for r in sub)}
    for subtype in sorted({r["incomplete_subtype"] for r in rows if I(r) and r["incomplete_subtype"]}):
        sub = [r for r in rows if I(r) and r["incomplete_subtype"] == subtype]
        out["by_incomplete_subtype"][subtype] = dict(Counter(r["decision"] for r in sub))
    for key, name in (("keyword_free", "by_keyword_free"), ("llm_assisted", "by_llm_assisted"), ("long_dossier", "by_long_dossier")):
        for value in (True, False):
            sub = [r for r in rows if r[key] is value]
            out[name][str(value)] = {"cases": len(sub), "fraud_recall": est.rate(sub, lambda r: r["detected"], F)["estimate"],
                                     "false_positive_rate": est.rate(sub, lambda r: r["detected"], LEGIT)["estimate"]}
    return out


# ------------------------------------------------------------------ API
def api_metrics(inputs: dict, est: Estimator) -> dict:
    requests, attempts, outputs = inputs["requests"], inputs["attempts"], inputs["outputs"]
    first = {}
    for a in attempts:
        if a["kind"] != "quota" and a["case_id"] not in first:
            first[a["case_id"]] = a["category"] is None
    ok_first = sum(first.values())
    valid = sum(o["gemini"]["status"] == "OK" for o in outputs)
    invalid = sum((o["gemini"]["failure_category"] or "") in INVALID_OUTPUT for o in outputs)
    latencies = [r["http_seconds"] for r in requests if r["status"] == "OK"]
    p95 = stats.bootstrap_quantile(latencies, 0.95, est.reps, est.seed)
    return {"requests_sent": len(requests), "requests_by_outcome": dict(Counter(r["category"] or "OK" for r in requests)),
            "M10_first_attempt_success": {"n": len(first), "successes": ok_first,
                                          "estimate": round(ok_first / len(first), 4) if first else None,
                                          "ci": stats.wilson(ok_first, len(first))},
            "M10_valid_answer_coverage": {"n": len(outputs), "successes": valid,
                                          "estimate": round(valid / len(outputs), 4) if outputs else None,
                                          "ci": stats.wilson(valid, len(outputs))},
            "M10_invalid_output_rate": {"n": len(outputs), "successes": invalid,
                                        "estimate": round(invalid / len(outputs), 4) if outputs else None,
                                        "ci": stats.wilson(invalid, len(outputs))},
            "retries_used": inputs["state"]["policy"]["retries_used"],
            "quota_pauses": sum(a["kind"] == "quota" for a in attempts),
            "transient_failures": sum(a["kind"] == "transient" for a in attempts),
            "model_versions": dict(Counter(str(r.get("model_version")) for r in requests if r["status"] == "OK")),
            "tokens": {k: sum(r.get(k) or 0 for r in requests) for k in ("prompt_tokens", "output_tokens", "thinking_tokens")},
            "M11_latency_seconds": {"successful_requests": len(latencies),
                                    "median": stats.bootstrap_quantile(latencies, 0.5, est.reps, est.seed),
                                    "p90": round(stats.quantile(latencies, 0.9), 3) if latencies else None,
                                    "p95": p95, "max": max(latencies) if latencies else None,
                                    "timeouts": sum(str(r["category"] or "").endswith("TIMEOUT") for r in requests)},
            "M11_latency_p95_seconds": {"estimate": p95["estimate"] if p95 else None, "ci": p95["ci"] if p95 else None}}


# ------------------------------------------------------------------ comparisons and trade-off
PAIRED = {"M1_fraud_recall": (lambda r: r["detected"], F), "M2_false_positive_rate": (lambda r: r["detected"], LEGIT),
          "M4_legitimate_approval_rate": (lambda r: r["approved"], L),
          "M7_unsafe_provisional_approvals": (lambda r: r["approved"], lambda r: F(r) or B(r) or INCOMPLETE(r))}


def paired(rows_a: List[dict], rows_b: List[dict], est: Estimator, name_a: str, name_b: str) -> dict:
    by_b = {r["case_id"]: r for r in rows_b}
    results, p_values = {}, {}
    for metric, (outcome, population) in PAIRED.items():
        pairs = [(r, by_b[r["case_id"]]) for r in rows_a if population(r)]
        b = sum(outcome(x) and not outcome(y) for x, y in pairs)
        c = sum(outcome(y) and not outcome(x) for x, y in pairs)
        groups = defaultdict(lambda: [0.0, 0])
        for x, y in pairs:
            groups[x["group"]][0] += int(outcome(x)) - int(outcome(y))
            groups[x["group"]][1] += 1
        n = len(pairs)
        diff = (sum(v[0] for v in groups.values()) / n) if n else None
        p = stats.mcnemar_exact(b, c)
        p_values[metric] = p
        results[metric] = {"cases": n, f"only_{name_a}": b, f"only_{name_b}": c,
                           "difference": round(diff, 4) if diff is not None else None,
                           "difference_ci": stats.ratio_bootstrap([tuple(v) for v in groups.values()], est.reps, est.seed),
                           "mcnemar_exact_p": p}
    adjusted = stats.holm(p_values)
    for metric, result in results.items():
        result["holm_p"] = adjusted[metric]
        ci = result["difference_ci"]
        significant = adjusted[metric] < 0.05 and ci is not None and (ci[0] > 0 or ci[1] < 0)
        result["claim"] = (f"{name_a} higher" if result["difference"] > 0 else f"{name_a} lower") if significant else \
            "no supported difference"
    return results


def tradeoff(rows_by_system: Dict[str, List[dict]], prevalences=(0.02, 0.05, 0.10)) -> dict:
    out = {}
    for system, rows in rows_by_system.items():
        fraud, legit = [r for r in rows if F(r)], [r for r in rows if LEGIT(r)]

        def rate(pop, key):
            return sum(bool(r[key]) for r in pop) / len(pop) if pop else 0.0
        counts = {"fraud_cases": len(fraud), "fraud_detected": sum(r["detected"] for r in fraud),
                  "fraud_provisionally_approved": sum(r["approved"] for r in fraud),
                  "fraud_activated_simulated": sum(r["activated"] for r in fraud),
                  "fraud_held_before_activation_simulated": sum(not r["activated"] for r in fraud),
                  "legitimate_cases": len(legit), "legitimate_provisionally_approved": sum(r["approved"] for r in legit),
                  "legitimate_information_requests": sum(r["nmi"] for r in legit),
                  "legitimate_flagged": sum(r["flag"] for r in legit), "legitimate_errors": sum(r["error"] for r in legit),
                  "legitimate_activated_simulated": sum(r["activated"] for r in legit)}
        counts["legitimate_delayed"] = counts["legitimate_cases"] - counts["legitimate_provisionally_approved"]
        per_1000 = {}
        for p in prevalences:
            per_1000[f"fraud_prevalence_{p:.0%}"] = {
                "fraud_detected": round(1000 * p * rate(fraud, "detected"), 1),
                "fraud_provisionally_approved": round(1000 * p * rate(fraud, "approved"), 1),
                "fraud_activated_simulated": round(1000 * p * rate(fraud, "activated"), 1),
                "legitimate_delayed": round(1000 * (1 - p) * (1 - rate(legit, "approved")), 1),
                "manual_reviews": round(1000 * (p * rate(fraud, "flag") + (1 - p) * rate(legit, "flag")), 1),
                "information_requests": round(1000 * (p * rate(fraud, "nmi") + (1 - p) * rate(legit, "nmi")), 1)}
        out[system] = {"counts": counts, "per_1000_campaigns": per_1000,
                       "note": "Re-weighted to assumed fraud prevalences; borderline cases are excluded from the re-weighting."}
    base, cand = out.get("hybrid_v2"), out.get("hybrid_v3")
    if base and cand:
        extra_fraud = cand["counts"]["fraud_detected"] - base["counts"]["fraud_detected"]
        extra_delay = cand["counts"]["legitimate_delayed"] - base["counts"]["legitimate_delayed"]
        out["hybrid_v3_vs_hybrid_v2"] = {"extra_fraud_detected": extra_fraud, "extra_legitimate_delayed": extra_delay,
                                         "extra_legitimate_delays_per_extra_fraud_detected":
                                             round(extra_delay / extra_fraud, 2) if extra_fraud > 0 else None}
    return out


# ------------------------------------------------------------------ criteria
def judge(entry: Optional[dict], bound: str, threshold: float) -> dict:
    if not entry or entry.get("estimate") is None:
        return {"result": "NOT_ESTIMABLE"}
    estimate, ci = entry["estimate"], entry.get("ci")
    if bound == "point":
        return {"result": "MET" if estimate <= threshold else "NOT_MET", "estimate": estimate, "ci": ci}
    point_ok = estimate >= threshold if bound == "lower" else estimate <= threshold
    if not point_ok:
        return {"result": "NOT_MET", "estimate": estimate, "ci": ci}
    bound_value = None if ci is None else (ci[0] if bound == "lower" else ci[1])
    bound_ok = bound_value is not None and (bound_value >= threshold if bound == "lower" else bound_value <= threshold)
    return {"result": "MET" if bound_ok else "INCONCLUSIVE", "estimate": estimate, "ci": ci, "bound_used": bound_value}


def evaluate_criteria(metrics: dict, api: dict, prereg: dict) -> dict:
    gates = {
        "G1_no_provisional_approval_of_incomplete_cases": metrics["M7I_unsafe_provisional_approvals_incomplete"],
        "G2_no_unsafe_activation_types_b_to_e": {"count": sum(metrics[k]["count"] for k in (
            "M8b_activations_with_unconfirmed_check", "M8c_activations_of_incomplete_cases",
            "M8d_activations_without_confirmation_record", "M8e_activations_via_campaign_supplied_contact"))},
        "G3_no_rejection_from_gemini_alone": metrics["G3_rejections_from_gemini_alone"],
        "G4_provisional_approval_never_activation": metrics["G4_provisional_approval_treated_as_activation"],
        "G5_no_campaign_supplied_confirmation_accepted": metrics["M9c_campaign_supplied_contacts_accepted"],
    }
    gate_results = {k: {"result": "PASS" if v["count"] == 0 else "FAIL", "count": v["count"],
                        "upper_95_case_level": v.get("upper_95_if_zero_case_level")} for k, v in gates.items()}
    criteria = {}
    for name, spec in prereg["success_criteria"]["criteria"].items():
        entry = metrics.get(spec["metric"]) or api.get(spec["metric"])
        criteria[name] = {"metric": spec["metric"], "bound": spec["bound"], "threshold": spec["threshold"],
                          **judge(entry, spec["bound"], spec["threshold"])}
    return {"gates": gate_results, "all_gates_pass": all(g["result"] == "PASS" for g in gate_results.values()),
            "criteria": criteria, "rule": prereg["success_criteria"]["rule"]}


# ------------------------------------------------------------------ driver
def score(run_dir: Path, label_file: Path, label_seal: Path, submission: Path, out_dir: Path,
          prereg_path: Path = config.PREREG_PATH) -> dict:
    out_dir = Path(out_dir).resolve()
    if (config.ROOT / "app").resolve() in out_dir.parents or out_dir == (config.ROOT / "app").resolve():
        raise SystemExit("Refusing to write scores inside app/")
    if out_dir.exists():
        raise SystemExit(f"{out_dir} exists; scores are written once")
    inputs = load_inputs(run_dir, label_file, label_seal, submission, prereg_path)
    est = Estimator(inputs["prereg"])
    rows = build_rows(inputs)
    complete = {s: [r for r in rs if r["gemini_valid"]] for s, rs in rows.items()}
    metrics = {s: system_metrics(rows[s], est) for s in config.SYSTEMS}
    api = api_metrics(inputs, est)
    result = {
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_status": inputs["state"]["status"], "run_reason": inputs["state"].get("reason"),
        "complete_run": inputs["state"]["status"] == "COMPLETE",
        "cases_scored": len(inputs["outputs"]), "cases_planned": len(inputs["manifest"]["case_order"]),
        "unprocessed_cases": len(inputs["manifest"]["case_order"]) - len(inputs["outputs"]),
        "label_agreement": {k: inputs["label_seal"].get(k) for k in ("kappa_truth_label", "kappa_documentation",
                                                                     "kappa_date_check", "status")},
        "strata": dict(Counter(r["stratum"] for r in rows["hybrid_v3"])),
        "population": "intent-to-treat (primary)",
        "metrics_itt": metrics,
        "metrics_complete_case": {s: system_metrics(complete[s], est) for s in ("hybrid_v3", "hybrid_v2")},
        "subgroups_hybrid_v3": subgroup_tables(rows["hybrid_v3"], est),
        "api": api,
        "criteria_hybrid_v3": evaluate_criteria(metrics["hybrid_v3"], api, inputs["prereg"]),
        "paired_hybrid_v3_vs_hybrid_v2": paired(rows["hybrid_v3"], rows["hybrid_v2"], est, "hybrid_v3", "hybrid_v2"),
        "paired_hybrid_v3_vs_v3_alone": paired(rows["hybrid_v3"], rows["v3_alone"], est, "hybrid_v3", "v3_alone"),
        "tradeoff": tradeoff(rows),
        "disclaimers": [inputs["prereg"]["analysis"]["simulation_disclaimer"],
                        inputs["prereg"]["retrieval"]["claim_restriction"],
                        f"Results apply to {inputs['prereg']['model']['id']} on the {inputs['prereg']['api_usage']['tier']} tier only.",
                        "Provisional approval (ELIGIBLE_PENDING_CONFIRMATION) is never counted as activation."],
    }
    out_dir.mkdir(parents=True)
    (out_dir / "scores.json").write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    with (out_dir / "case_level.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "group", "category", "stratum", "truth", "documentation"] +
                        [f"{s}_{k}" for s in config.SYSTEMS for k in ("decision", "activated_simulated")])
        by_case = {s: {r["case_id"]: r for r in rs} for s, rs in rows.items()}
        for r in rows["hybrid_v3"]:
            writer.writerow([r["case_id"], r["group"], r["category"], r["stratum"], r["truth"], r["documentation"]] +
                            [x for s in config.SYSTEMS for x in (by_case[s][r["case_id"]]["decision"],
                                                                  by_case[s][r["case_id"]]["activated"])])
    (out_dir / "report.md").write_text(render(result), encoding="utf-8")
    return result


def _fmt(entry: Optional[dict]) -> str:
    if not entry or entry.get("estimate") is None:
        return "n/a"
    ci = entry.get("ci")
    return f"{entry['estimate']:.3f} ({ci[0]:.3f}–{ci[1]:.3f}) n={entry.get('n')}" if ci else f"{entry['estimate']:.3f} n={entry.get('n')}"


def render(result: dict) -> str:
    lines = ["# v5 independent evaluation: scores", "",
             f"Run status: **{result['run_status']}** ({result['cases_scored']} of {result['cases_planned']} cases scored). "
             f"Primary population: {result['population']}.", ""]
    lines += [f"> {d}" for d in result["disclaimers"]] + [""]
    crit = result["criteria_hybrid_v3"]
    lines += ["## Safety gates (hybrid v3)", "", "| Gate | Result | Count |", "|---|---|---|"]
    lines += [f"| {k} | {v['result']} | {v['count']} |" for k, v in crit["gates"].items()]
    lines += ["", "## Pre-registered criteria (hybrid v3)", "", "| Criterion | Result | Estimate (95% CI) | Threshold |",
              "|---|---|---|---|"]
    for name, c in crit["criteria"].items():
        ci = c.get("ci")
        shown = f"{c.get('estimate')} ({ci[0]}–{ci[1]})" if ci else str(c.get("estimate"))
        lines.append(f"| {name} | {c['result']} | {shown} | {c['bound']} {c['threshold']} |")
    lines += ["", "## Key metrics by system (intent-to-treat)", "", "| Metric | hybrid_v3 | hybrid_v2 | v3_alone |", "|---|---|---|---|"]
    for key in ("M1_fraud_recall", "M1a_dossier_detectable_fraud_recall", "M2_false_positive_rate", "M3_fraud_precision",
                "M4_legitimate_approval_rate", "M5_information_request_rate", "M6_manual_review_rate",
                "M7F_unsafe_provisional_approvals_fraud", "M8a_fraud_activations_simulated"):
        lines.append(f"| {key} | " + " | ".join(_fmt(result["metrics_itt"][s][key]) for s in config.SYSTEMS) + " |")
    lines += ["", "## Paired comparison: hybrid v3 vs hybrid v2 (case level)", "",
              "| Metric | Difference (95% CI) | Exact McNemar p | Holm p | Claim |", "|---|---|---|---|---|"]
    for k, v in result["paired_hybrid_v3_vs_hybrid_v2"].items():
        lines.append(f"| {k} | {v['difference']} ({v['difference_ci']}) | {v['mcnemar_exact_p']} | {v['holm_p']} | {v['claim']} |")
    t = result["tradeoff"]
    lines += ["", "## Trade-off: fraud prevented vs legitimate applicants delayed", "",
              "| System | Fraud detected | Fraud provisionally approved | Fraud activated (sim.) | Legitimate delayed | Legitimate activated (sim.) |",
              "|---|---|---|---|---|---|"]
    for s in config.SYSTEMS:
        c = t[s]["counts"]
        lines.append(f"| {s} | {c['fraud_detected']}/{c['fraud_cases']} | {c['fraud_provisionally_approved']} | "
                     f"{c['fraud_activated_simulated']} | {c['legitimate_delayed']}/{c['legitimate_cases']} | "
                     f"{c['legitimate_activated_simulated']} |")
    if "hybrid_v3_vs_hybrid_v2" in t:
        lines += ["", f"hybrid v3 vs hybrid v2: {t['hybrid_v3_vs_hybrid_v2']}"]
    api = result["api"]
    lines += ["", "## API reliability and latency", "",
              f"Requests sent: {api['requests_sent']}; outcomes: {api['requests_by_outcome']}; retries used: "
              f"{api['retries_used']}; quota pauses: {api['quota_pauses']}; model versions: {api['model_versions']}.",
              f"First-attempt success: {_fmt(api['M10_first_attempt_success'])}; valid-answer coverage: "
              f"{_fmt(api['M10_valid_answer_coverage'])}; latency p95: {api['M11_latency_p95_seconds']}.", ""]
    return "\n".join(lines) + "\n"
