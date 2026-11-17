"""Scoring pipeline for the v5 independent test (standard library only; never imports `app`).

Reads, never writes: the run directory, the adjudicated labels and their seal, the submission and the
pre-registration.  Writes only into a new output directory outside app/.  Every metric, criterion, interval and
comparison is the pre-registered one (evaluation/independent_test_v5/preregistration.json).

Statistical structure (pre-registered):
  * safety gates G1-G5 - zero observed events, with one-sided upper bounds (zero events never prove a zero rate);
  * one primary endpoint H1 and two key secondary criteria K1, K2 - together with the gates they form the verdict
    (intersection-union, so no multiplicity adjustment is needed for the verdict);
  * research target R1 - assessed only if H1 is met (fixed sequence);
  * comparisons with hybrid v2 - one Holm-adjusted family of cluster sign-flip tests; a fairness non-inferiority
    assessment with a pre-set margin;
  * everything else descriptive, with intervals; no claim from any single descriptive metric.
"""
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import config, labels as label_io, stats

ELIGIBLE = "ELIGIBLE_PENDING_CONFIRMATION"
INDEPENDENT = {"OFFICIAL_REGISTRY", "OFFICIAL_DIRECTORY", "PLATFORM_KYC", "PRIOR_VERIFIED_RECORD"}
REQUIRED = {"BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION"}
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


def _environment_facts(case: dict, tolerance: float) -> dict:
    env = case.get("external_environment") or {}
    goal = case["input"]["goal_amount"]
    cost = env.get("COST_ISSUER") or {}
    stated, other = cost.get("amount_stated_inr"), cost.get("other_payers_inr") or 0
    issuer_contradicts = cost.get("independent_response") == "CONTRADICTED" or (
        stated is not None and goal > (stated - other) * (1 + tolerance))
    return {"required_party_reveals": any((env.get(p) or {}).get("independent_response") != "CONFIRMED" for p in REQUIRED),
            "cost_issuer_reveals": issuer_contradicts,
            "assisted_route_resolvable": cost.get("independent_response") == "CONFIRMED" and stated is not None
                                         and goal <= (stated - other) * (1 + tolerance)}


def build_rows(inputs: dict) -> Dict[str, List[dict]]:
    """One row per case per system, joining sealed labels with run outputs."""
    missing = sorted(o["case_id"] for o in inputs["outputs"] if o["case_id"] not in inputs["labels"])
    if missing:
        raise SystemExit(f"Refusing to score: cases without adjudicated labels {missing}")
    rows = {s: [] for s in config.SYSTEMS}
    detection = set(inputs["prereg"]["analysis"]["detection"])
    tolerance = inputs["prereg"]["analysis"]["amount_check_tolerance"]
    for output in inputs["outputs"]:
        label = inputs["labels"][output["case_id"]]
        case = inputs["cases"][output["case_id"]]
        base = {"case_id": output["case_id"], "group": output["scenario_group"], "category": output["category"],
                "beneficiary_type": case["input"].get("beneficiary_type"),
                "truth": label["truth_label"], "documentation": label["documentation"],
                "stratum": config.stratum(label["truth_label"], label["documentation"]),
                "dossier_detectable": label["detectable_from_dossier"] == "yes",
                "mechanism": case.get("mechanism"), "keyword_free": bool(case.get("keyword_free")),
                "incomplete_subtype": case.get("incomplete_subtype"), "llm_assisted": bool(case.get("llm_assisted")),
                "gemini_valid": output["gemini"]["status"] == "OK",
                "long_dossier": output["retrieval"]["total_chunks"] > 5,
                "all_chunks_retrieved": output["retrieval"]["all_chunks_retrieved"],
                **_environment_facts(case, tolerance)}
        for system in config.SYSTEMS:
            result = output["systems"][system]
            sim = result["confirmation_simulated"]
            amount = result.get("amount_check_simulated") or {}
            decision = result["decision"]
            independent_confirmed = {s["check"] for s in sim["satisfied"]
                                     if s["source"] in INDEPENDENT and s["outcome"] == "CONFIRMED"}
            final = REQUIRED <= set(sim["required_checks"]) and REQUIRED <= independent_confirmed and not sim["pending_checks"]
            rows[system].append({**base, "decision": decision, "detected": decision in detection,
                                 "approved": decision == "APPROVED", "nmi": decision == "NEEDS_MORE_INFORMATION",
                                 "flag": decision == "FLAG_FOR_REVIEW", "error": decision == "VERIFICATION_ERROR",
                                 "rejected": decision == "REJECTED", "triggers": result.get("triggers") or [],
                                 "review_basis": result.get("review_basis"), "workflow_state": result["workflow_state"],
                                 "initial_state": sim["initial_state"],
                                 "provisional": decision == "APPROVED" and sim["initial_state"] == ELIGIBLE,
                                 "independent_confirmations": len(independent_confirmed & REQUIRED),
                                 "final_approved": final, "activated": sim["activated"],
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
        self.size_rule, self.floor = a.get("cluster_size_rule", "kish"), a.get("icc_floor", 0.0)

    def rate(self, rows: List[dict], numerator: Callable[[dict], bool], denominator: Callable[[dict], bool]) -> dict:
        den = [r for r in rows if denominator(r)]
        groups = defaultdict(list)
        for r in den:
            groups[r["group"]].append(int(bool(numerator(r))))
        primary = stats.clustered_proportion(dict(groups), self.size_rule, self.floor)
        primary["bootstrap_ci"] = stats.ratio_bootstrap([(sum(v), len(v)) for v in groups.values()], self.reps, self.seed)
        votes = [int(sum(v) * 2 > len(v)) for v in groups.values() if v]
        primary["group_level"] = {"groups": len(votes), "majority_rate": round(sum(votes) / len(votes), 4) if votes else None,
                                  "ci": stats.wilson(sum(votes), len(votes))}
        return primary

    def count(self, rows: List[dict], predicate: Callable[[dict], bool], population: Callable[[dict], bool]) -> dict:
        """Event count with the one-sided 95% upper bound on the effective sample size (ICC = 1 when no events)."""
        pop = [r for r in rows if population(r)]
        events = [r["case_id"] for r in pop if predicate(r)]
        groups = defaultdict(list)
        for r in pop:
            groups[r["group"]].append(int(bool(predicate(r))))
        clustered = stats.clustered_proportion(dict(groups), self.size_rule, self.floor) if pop else {}
        n_eff = clustered.get("effective_n")
        return {"count": len(events), "cases": events, "population_cases": len(pop), "population_groups": len(groups),
                "effective_n": n_eff, "one_sided_95_upper": stats.zero_event_upper(n_eff) if pop and not events else None,
                "rate_ci": clustered.get("ci")}


F = lambda r: r["stratum"] == "F"
L = lambda r: r["stratum"] == "L"
I = lambda r: r["stratum"] == "I"
B = lambda r: r["stratum"] == "B"
LEGIT = lambda r: r["stratum"] in ("L", "I")
INCOMPLETE = lambda r: r["documentation"] == "incomplete"
GBI = lambda r: I(r) and r["incomplete_subtype"] == "genuine_but_informal"
ALL = lambda r: True


def unsafe_activation(r: dict) -> Dict[str, bool]:
    if not r["activated"]:
        return {"a": False, "b": False, "c": False, "d": False, "e": False}
    return {"a": r["truth"] == "fraudulent",
            "b": (not r["activation_allowed"]) or (not r["final_approved"]) or bool(r["pending_checks"]) or
                 any(s["source"] not in INDEPENDENT or s["outcome"] != "CONFIRMED" for s in r["satisfied"]),
            "c": r["documentation"] == "incomplete",
            "d": r["confirmation_records"] == 0 or any(t != "confirmation" for t in r["activation_triggers"]),
            "e": r["campaign_supplied_satisfied"] > 0}


def stage_funnel(rows: List[dict]) -> dict:
    out = {}
    for s in "LIFB":
        sub = [r for r in rows if r["stratum"] == s]
        out[s] = {"cases": len(sub), "S1_provisional_approval": sum(r["provisional"] for r in sub),
                  "S2_checks_independently_confirmed": dict(Counter(r["independent_confirmations"] for r in sub if r["provisional"])),
                  "S3_final_approval": sum(r["final_approved"] for r in sub), "S4_activation": sum(r["activated"] for r in sub),
                  "activation_without_final_approval": sum(r["activated"] and not r["final_approved"] for r in sub),
                  "final_approval_without_activation": sum(r["final_approved"] and not r["activated"] for r in sub)}
    return out


def system_metrics(rows: List[dict], est: Estimator) -> dict:
    unsafe = {r["case_id"]: unsafe_activation(r) for r in rows}
    fraud_activated = [r for r in rows if F(r) and r["activated"]]
    m = {
        "M1_fraud_recall": est.rate(rows, lambda r: r["detected"], F),
        "M1a_dossier_detectable_fraud_recall": est.rate(rows, lambda r: r["detected"], lambda r: F(r) and r["dossier_detectable"]),
        "M1b_fraud_held_before_activation_simulated": est.rate(rows, lambda r: not r["activated"], F),
        "M2_false_positive_rate": est.rate(rows, lambda r: r["detected"], LEGIT),
        "M3_fraud_precision": est.rate(rows, F, lambda r: r["detected"] and (F(r) or LEGIT(r))),
        "M3s_fraud_precision_borderline_as_negative": est.rate(rows, F, lambda r: r["detected"]),
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
        "M8_unsafe_activations": {
            "all_types": est.count(rows, lambda r: any(unsafe[r["case_id"]].values()), ALL),
            "among_fraud": est.count(rows, lambda r: r["activated"], F),
            **{f"type_{t}": est.count(rows, lambda r, t=t: unsafe[r["case_id"]][t], ALL) for t in "abcde"},
            "type_a_decomposition": {
                "revealable_only_by_cost_issuer": sorted(r["case_id"] for r in fraud_activated if r["cost_issuer_reveals"]),
                "revealed_by_no_independent_party": sorted(r["case_id"] for r in fraud_activated if not r["cost_issuer_reveals"]),
                "caught_by_simulated_amount_check": sorted(r["case_id"] for r in fraud_activated if r["amount_outcome"] == "CONTRADICTED")}},
        "S_stage_funnel": stage_funnel(rows),
        "M9a_fraud_passing_confirmation_simulated": est.rate(rows, lambda r: r["activated"], lambda r: F(r) and r["provisional"]),
        "M9b_legitimate_blocked_at_confirmation_simulated": est.rate(rows, lambda r: not r["activated"],
                                                                     lambda r: LEGIT(r) and r["provisional"]),
        "M9c_campaign_supplied_contacts_accepted": est.count(rows, lambda r: r["campaign_supplied_satisfied"] > 0, ALL),
        "M9d_amount_check_simulated": {
            "amount_inflation_fraud_contradicted": est.rate(rows, lambda r: r["amount_outcome"] == "CONTRADICTED",
                                                            lambda r: F(r) and r["mechanism"] == "amount_inflation" and r["activated"]),
            "fraud_contradicted": est.rate(rows, lambda r: r["amount_outcome"] == "CONTRADICTED", lambda r: F(r) and r["activated"]),
            "legitimate_contradicted": est.rate(rows, lambda r: r["amount_outcome"] == "CONTRADICTED", lambda r: LEGIT(r) and r["activated"]),
            "open_undisclosed": est.rate(rows, lambda r: r["amount_outcome"] == "OPEN", lambda r: r["activated"])},
        "N1_non_dossier_detectable_fraud": {
            "overall": {k: est.rate(rows, f, lambda r: F(r) and not r["dossier_detectable"]) for k, f in (
                ("detected", lambda r: r["detected"]), ("provisionally_approved", lambda r: r["approved"]),
                ("held_before_activation_simulated", lambda r: not r["activated"]))},
            "by_mechanism": {mech: dict(Counter(r["decision"] for r in rows if F(r) and not r["dossier_detectable"]
                                                and r["mechanism"] == mech))
                             for mech in sorted({r["mechanism"] for r in rows if F(r) and r["mechanism"]})}},
        "F1_genuine_but_informal_outcomes": {k: est.rate(rows, f, GBI) for k, f in (
            ("approved", lambda r: r["approved"]), ("information_request", lambda r: r["nmi"]),
            ("flagged", lambda r: r["flag"]), ("rejected", lambda r: r["rejected"]), ("error", lambda r: r["error"]))},
        "F1_genuine_but_informal_escalation": est.rate(rows, lambda r: r["flag"] or r["rejected"], GBI),
        "F2_assisted_route_resolvable": est.rate(rows, lambda r: r["assisted_route_resolvable"], GBI),
        "F3_legitimate_outcomes_by_group": _by_group(rows, est),
        "G3_rejections_from_gemini_alone": est.count(
            rows, lambda r: r["rejected"] and r["triggers"] and all(str(t).upper().startswith("GEMINI") for t in r["triggers"]), ALL),
        "G4_provisional_approval_treated_as_activation": est.count(
            rows, lambda r: r["approved"] and (r["workflow_state"] != ELIGIBLE or r["initial_state"] != ELIGIBLE), ALL),
        "decisions": {s: dict(Counter(r["decision"] for r in rows if r["stratum"] == s)) for s in "LIFB"},
    }
    return m


def _by_group(rows: List[dict], est: Estimator) -> dict:
    out = {}
    for key in ("category", "beneficiary_type"):
        table = {}
        for value in sorted({str(r[key]) for r in rows if LEGIT(r)}):
            sub = [r for r in rows if str(r[key]) == value]
            table[value] = {"legitimate_approval": est.rate(sub, lambda r: r["approved"], LEGIT)["estimate"],
                            "legitimate_information_request": est.rate(sub, lambda r: r["nmi"], LEGIT)["estimate"],
                            "legitimate_cases": sum(LEGIT(r) for r in sub)}
        rates = [v["legitimate_approval"] for v in table.values() if v["legitimate_approval"] is not None]
        ratio = round(min(rates) / max(rates), 3) if rates and max(rates) > 0 else None
        out[key] = {"groups": table, "lowest_to_highest_approval_ratio": ratio,
                    "screening_flag": ratio is not None and ratio < 0.8}
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

    def share(x, n):
        return {"n": n, "successes": x, "estimate": round(x / n, 4) if n else None, "ci": stats.wilson(x, n)}
    return {"requests_sent": len(requests), "requests_by_outcome": dict(Counter(r["category"] or "OK" for r in requests)),
            "M10_first_attempt_success": share(ok_first, len(first)),
            "M10_valid_answer_coverage": share(valid, len(outputs)),
            "M10_invalid_output_rate": share(invalid, len(outputs)),
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


# ------------------------------------------------------------------ comparisons, fairness and trade-off
FAMILY = {"fraud_provisional_approvals": (lambda r: r["approved"], F),
          "legitimate_complete_approvals": (lambda r: r["approved"], L),
          "dossier_detectable_fraud_recall": (lambda r: r["detected"], lambda r: F(r) and r["dossier_detectable"]),
          "false_positive_rate": (lambda r: r["detected"], LEGIT)}


def _paired_groups(rows_a, rows_b, outcome, population):
    by_b = {r["case_id"]: r for r in rows_b}
    groups = defaultdict(lambda: [0, 0, 0])            # discordant a-only, b-only, cases
    for r in rows_a:
        if population(r):
            x, y = int(bool(outcome(r))), int(bool(outcome(by_b[r["case_id"]])))
            g = groups[r["group"]]
            g[0] += x and not y
            g[1] += y and not x
            g[2] += 1
    return groups


def paired(rows_a: List[dict], rows_b: List[dict], est: Estimator, name_a: str, name_b: str) -> dict:
    results, p_values = {}, {}
    for metric, (outcome, population) in FAMILY.items():
        groups = _paired_groups(rows_a, rows_b, outcome, population)
        n = sum(g[2] for g in groups.values())
        b, c = sum(g[0] for g in groups.values()), sum(g[1] for g in groups.values())
        p = stats.cluster_sign_flip_test([g[0] - g[1] for g in groups.values()])
        p_values[metric] = p
        diff = (b - c) / n if n else None
        results[metric] = {"cases": n, "groups": len(groups), f"only_{name_a}": b, f"only_{name_b}": c,
                           "difference": round(diff, 4) if diff is not None else None,
                           "difference_ci": stats.ratio_bootstrap([(g[0] - g[1], g[2]) for g in groups.values()],
                                                                  est.reps, est.seed),
                           "cluster_sign_flip_p": p}
    adjusted = stats.holm(p_values)
    for metric, result in results.items():
        result["holm_p"] = adjusted[metric]
        ci = result["difference_ci"]
        supported = adjusted[metric] < 0.05 and ci is not None and (ci[0] > 0 or ci[1] < 0)
        result["claim"] = (f"{name_a} higher" if result["difference"] > 0 else f"{name_a} lower") if supported else \
            "no supported difference"
    return results


def fairness_noninferiority(rows_v3, rows_v2, est: Estimator, margin: float) -> dict:
    groups = _paired_groups(rows_v3, rows_v2, lambda r: r["approved"], L)
    n = sum(g[2] for g in groups.values())
    if not n:
        return {"result": "NOT_ESTIMABLE"}
    diff = sum(g[0] - g[1] for g in groups.values()) / n
    ci = stats.ratio_bootstrap([(g[0] - g[1], g[2]) for g in groups.values()], est.reps, est.seed)
    result = "NON_INFERIOR" if ci[0] > margin else "INFERIOR" if ci[1] < margin else "INCONCLUSIVE"
    return {"metric": "legitimate-complete provisional approval, hybrid_v3 minus hybrid_v2", "cases": n,
            "difference": round(diff, 4), "ci": ci, "margin": margin, "result": result}


def tradeoff(rows_by_system: Dict[str, List[dict]], est: Estimator, prevalences=(0.02, 0.05, 0.10)) -> dict:
    out = {}
    for system, rows in rows_by_system.items():
        fraud, legit = [r for r in rows if F(r)], [r for r in rows if LEGIT(r)]

        def rate(pop, key):
            return sum(bool(r[key]) for r in pop) / len(pop) if pop else 0.0
        counts = {"fraud_cases": len(fraud), "fraud_detected": sum(r["detected"] for r in fraud),
                  "fraud_provisionally_approved": sum(r["approved"] for r in fraud),
                  "fraud_final_approved_simulated": sum(r["final_approved"] for r in fraud),
                  "fraud_activated_simulated": sum(r["activated"] for r in fraud),
                  "legitimate_cases": len(legit), "legitimate_provisionally_approved": sum(r["approved"] for r in legit),
                  "legitimate_information_requests": sum(r["nmi"] for r in legit),
                  "legitimate_flagged": sum(r["flag"] for r in legit), "legitimate_errors": sum(r["error"] for r in legit),
                  "legitimate_activated_simulated": sum(r["activated"] for r in legit)}
        counts["legitimate_delayed"] = counts["legitimate_cases"] - counts["legitimate_provisionally_approved"]
        per_1000 = {}
        recall = est.rate(rows, lambda r: r["detected"], F)
        fpr = est.rate(rows, lambda r: r["detected"], LEGIT)
        for p in prevalences:
            ppv = None
            if recall["estimate"] is not None and fpr["estimate"] is not None:
                def _ppv(sens, fp):
                    return round(p * sens / (p * sens + (1 - p) * fp), 4) if (p * sens + (1 - p) * fp) else None
                ppv = {"estimate": _ppv(recall["estimate"], fpr["estimate"]),
                       "conservative_bounds": [_ppv(recall["ci"][0], fpr["ci"][1]), _ppv(recall["ci"][1], fpr["ci"][0])]}
            per_1000[f"fraud_prevalence_{p:.0%}"] = {
                "fraud_detected": round(1000 * p * rate(fraud, "detected"), 1),
                "fraud_provisionally_approved": round(1000 * p * rate(fraud, "approved"), 1),
                "fraud_activated_simulated": round(1000 * p * rate(fraud, "activated"), 1),
                "legitimate_delayed": round(1000 * (1 - p) * (1 - rate(legit, "approved")), 1),
                "manual_reviews": round(1000 * (p * rate(fraud, "flag") + (1 - p) * rate(legit, "flag")), 1),
                "information_requests": round(1000 * (p * rate(fraud, "nmi") + (1 - p) * rate(legit, "nmi")), 1),
                "precision_ppv": ppv}
        out[system] = {"counts": counts, "per_1000_campaigns": per_1000,
                       "note": "Re-weighted to assumed fraud prevalences; borderline cases are excluded from the re-weighting."}
    out["hybrid_v3_vs_hybrid_v2"] = _tradeoff_ratio(rows_by_system["hybrid_v3"], rows_by_system["hybrid_v2"], est)
    out["retrospective_context"] = ("In-sample retrospective benchmark (750 cases, clean Gemini approval assumed): "
                                    "fraudulent provisional approvals 64 -> 20, legitimate approvals 231 -> 162. Context only.")
    return out


def _tradeoff_ratio(rows_v3, rows_v2, est: Estimator) -> dict:
    """Legitimate approvals lost per fraudulent provisional approval prevented (hybrid v2 -> v3), paired."""
    by_v2 = {r["case_id"]: r for r in rows_v2}
    groups = defaultdict(lambda: [0, 0])
    for r in rows_v3:
        v2 = by_v2[r["case_id"]]
        if L(r):
            groups[r["group"]][0] += int(v2["approved"]) - int(r["approved"])        # legitimate approvals lost
        if F(r):
            groups[r["group"]][1] += int(v2["approved"]) - int(r["approved"])        # fraud provisional approvals prevented
    lost, prevented = sum(g[0] for g in groups.values()), sum(g[1] for g in groups.values())
    rng, values, prevented_draws = random.Random(est.seed), [], []
    clusters = list(groups.values())
    for _ in range(est.reps if clusters else 0):
        sample = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        a, b = sum(s[0] for s in sample), sum(s[1] for s in sample)
        prevented_draws.append(b)
        if b > 0:
            values.append(a / b)
    prevented_draws.sort()
    k = len(prevented_draws)
    prevented_ci = (prevented_draws[int(0.025 * (k - 1))], prevented_draws[-(-975 * (k - 1) // 1000)]) if k else None
    values.sort()
    ratio_ci = (round(values[int(0.025 * (len(values) - 1))], 3), round(values[int(0.975 * (len(values) - 1))], 3)) \
        if values and prevented_ci and prevented_ci[0] > 0 else None
    return {"legitimate_complete_approvals_lost": lost, "fraud_provisional_approvals_prevented": prevented,
            "prevented_bootstrap_ci": prevented_ci,
            "legitimate_lost_per_fraud_prevented": round(lost / prevented, 3) if prevented > 0 else None,
            "ratio_ci": ratio_ci,
            "ratio_reported": bool(ratio_ci),
            "rule": "The ratio interval is reported only when the interval for frauds prevented excludes 0."}


# ------------------------------------------------------------------ criteria and verdict
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
    return {"result": "MET" if bound_ok else "INCONCLUSIVE", "estimate": estimate, "ci": ci, "bound_used": bound_value,
            "effective_n": entry.get("effective_n"), "design_effect": entry.get("design_effect")}


def _judge_all(specs: dict, metrics: dict, api: dict) -> dict:
    out = {}
    for name, spec in specs.items():
        entry = metrics.get(spec["metric"]) or api.get(spec["metric"])
        out[name] = {"metric": spec["metric"], "bound": spec["bound"], "threshold": spec["threshold"],
                     **judge(entry, spec["bound"], spec["threshold"])}
    return out


def evaluate_criteria(metrics: dict, api: dict, prereg: dict) -> dict:
    criteria = prereg["success_criteria"]
    gate_entries = {
        "G1_no_provisional_approval_of_incomplete_cases": metrics["M7I_unsafe_provisional_approvals_incomplete"],
        "G2_no_unsafe_activation": metrics["M8_unsafe_activations"]["all_types"],
        "G3_no_rejection_from_gemini_alone": metrics["G3_rejections_from_gemini_alone"],
        "G4_provisional_approval_never_activation": metrics["G4_provisional_approval_treated_as_activation"],
        "G5_no_campaign_supplied_confirmation_accepted": metrics["M9c_campaign_supplied_contacts_accepted"],
    }
    gates = {k: {"result": "PASS" if v["count"] == 0 else "FAIL", "count": v["count"], "cases": v["cases"],
                 "population_cases": v["population_cases"], "effective_n": v["effective_n"],
                 "one_sided_95_upper_if_zero": v["one_sided_95_upper"]} for k, v in gate_entries.items()}
    fraud_activation = metrics["M8_unsafe_activations"]["among_fraud"]
    gates["G2_no_unsafe_activation"]["fraud_population_upper_if_zero"] = fraud_activation["one_sided_95_upper"]
    gates["G2_no_unsafe_activation"]["type_counts"] = {t: metrics["M8_unsafe_activations"][f"type_{t}"]["count"] for t in "abcde"}
    primary = _judge_all(criteria["primary_endpoint"], metrics, api)
    key = _judge_all(criteria["key_secondary"], metrics, api)
    components = [g["result"] for g in gates.values()] + [c["result"] for c in list(primary.values()) + list(key.values())]
    if any(c in ("FAIL", "NOT_MET", "NOT_ESTIMABLE") for c in components):
        verdict = "DOES_NOT_MEET_MINIMUM_STANDARD"
    elif any(c == "INCONCLUSIVE" for c in components):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "MEETS_MINIMUM_STANDARD"
    h1_met = all(c["result"] == "MET" for c in primary.values())
    research = {name: ({"metric": spec["metric"], "threshold": spec["threshold"], **judge(metrics.get(spec["metric"]), spec["bound"], spec["threshold"])}
                       if h1_met else {"result": "NOT_ASSESSED", "reason": "fixed sequence: H1 not met"})
                for name, spec in criteria["research_target"].items()}
    return {"verdict": verdict, "gates": gates, "all_gates_pass": all(g["result"] == "PASS" for g in gates.values()),
            "primary_endpoint": primary, "key_secondary": key, "research_target": research,
            "secondary_benchmarks_descriptive": _judge_all(criteria["secondary_benchmarks_descriptive"], metrics, api),
            "operational_api_descriptive": _judge_all(criteria["operational_api_descriptive"], metrics, api),
            "rule": criteria["evaluation_rule"], "multiplicity_note": criteria["multiplicity_note"],
            "zero_event_interpretation": criteria["gates"]["interpretation"]}


# ------------------------------------------------------------------ driver
def score(run_dir: Path, label_file: Path, label_seal: Path, submission: Path, out_dir: Path,
          prereg_path: Path = config.PREREG_PATH) -> dict:
    out_dir = Path(out_dir).resolve()
    if (config.ROOT / "app").resolve() in out_dir.parents or out_dir == (config.ROOT / "app").resolve():
        raise SystemExit("Refusing to write scores inside app/")
    if out_dir.exists():
        raise SystemExit(f"{out_dir} exists; scores are written once")
    inputs = load_inputs(run_dir, label_file, label_seal, submission, prereg_path)
    prereg = inputs["prereg"]
    est = Estimator(prereg)
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
        "dossier_detectable_fraud_groups": len({r["group"] for r in rows["hybrid_v3"] if F(r) and r["dossier_detectable"]}),
        "population": "intent-to-treat (primary)",
        "interval_method": prereg["analysis"]["primary_interval"],
        "criteria_hybrid_v3": evaluate_criteria(metrics["hybrid_v3"], api, prereg),
        "metrics_itt": metrics,
        "metrics_complete_case": {s: system_metrics(complete[s], est) for s in ("hybrid_v3", "hybrid_v2")},
        "comparisons_hybrid_v3_vs_hybrid_v2": paired(rows["hybrid_v3"], rows["hybrid_v2"], est, "hybrid_v3", "hybrid_v2"),
        "comparisons_hybrid_v3_vs_v3_alone_descriptive": paired(rows["hybrid_v3"], rows["v3_alone"], est, "hybrid_v3", "v3_alone"),
        "fairness_noninferiority": fairness_noninferiority(rows["hybrid_v3"], rows["hybrid_v2"], est,
                                                           prereg["success_criteria"]["fairness_noninferiority"]["margin"]),
        "tradeoff": tradeoff(rows, est),
        "api": api,
        "disclaimers": [prereg["analysis"]["simulation_disclaimer"], prereg["retrieval"]["claim_restriction"],
                        f"Results apply to {prereg['model']['id']} on the {prereg['api_usage']['tier']} tier only.",
                        "Provisional approval (ELIGIBLE_PENDING_CONFIRMATION) is never counted as final approval or activation.",
                        "Zero observed events never establish a zero population rate; see the one-sided upper bounds."],
    }
    out_dir.mkdir(parents=True)
    (out_dir / "scores.json").write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    with (out_dir / "case_level.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "group", "category", "stratum", "truth", "documentation"] +
                        [f"{s}_{k}" for s in config.SYSTEMS for k in ("decision", "final_approved_sim", "activated_sim")])
        by_case = {s: {r["case_id"]: r for r in rs} for s, rs in rows.items()}
        for r in rows["hybrid_v3"]:
            writer.writerow([r["case_id"], r["group"], r["category"], r["stratum"], r["truth"], r["documentation"]] +
                            [x for s in config.SYSTEMS for x in (by_case[s][r["case_id"]]["decision"],
                                                                  by_case[s][r["case_id"]]["final_approved"],
                                                                  by_case[s][r["case_id"]]["activated"])])
    (out_dir / "report.md").write_text(render(result), encoding="utf-8")
    return result


def _fmt(entry: Optional[dict]) -> str:
    if not entry or entry.get("estimate") is None:
        return "n/a"
    ci = entry.get("ci")
    tail = f" n={entry.get('n')}, n_eff={entry.get('effective_n')}"
    return f"{entry['estimate']:.3f} ({ci[0]:.3f}–{ci[1]:.3f}){tail}" if ci else f"{entry['estimate']:.3f}{tail}"


def render(result: dict) -> str:
    crit = result["criteria_hybrid_v3"]
    lines = ["# v5 independent evaluation: scores", "",
             f"Run status: **{result['run_status']}** ({result['cases_scored']} of {result['cases_planned']} cases scored). "
             f"Primary population: {result['population']}. Verdict: **{crit['verdict']}**.", ""]
    lines += [f"> {d}" for d in result["disclaimers"]] + ["", f"Interval method: {result['interval_method']}", ""]
    lines += ["## Safety gates (zero tolerance, observed)", "", "| Gate | Result | Count | One-sided 95% upper bound if zero |",
              "|---|---|---|---|"]
    lines += [f"| {k} | {v['result']} | {v['count']} | {v['one_sided_95_upper_if_zero']} |" for k, v in crit["gates"].items()]
    lines += ["", "## Primary endpoint, key secondary criteria and research target (hybrid v3)", "",
              "| Item | Result | Estimate (95% CI) | Threshold | n_eff |", "|---|---|---|---|---|"]
    for section in ("primary_endpoint", "key_secondary", "research_target"):
        for name, c in crit[section].items():
            ci = c.get("ci")
            shown = f"{c.get('estimate')} ({ci[0]}–{ci[1]})" if ci else str(c.get("estimate", ""))
            lines.append(f"| {name} | {c['result']} | {shown} | {c.get('bound', '')} {c.get('threshold', '')} | {c.get('effective_n', '')} |")
    lines += ["", "## Descriptive benchmarks (no claim from any single item)", "", "| Benchmark | Result | Estimate |", "|---|---|---|"]
    for section in ("secondary_benchmarks_descriptive", "operational_api_descriptive"):
        for name, c in crit[section].items():
            lines.append(f"| {name} | {c['result']} | {c.get('estimate')} |")
    lines += ["", "## Key metrics by system (intent-to-treat)", "", "| Metric | hybrid_v3 | hybrid_v2 | v3_alone |", "|---|---|---|---|"]
    for key in ("M1_fraud_recall", "M1a_dossier_detectable_fraud_recall", "M2_false_positive_rate", "M3_fraud_precision",
                "M4_legitimate_approval_rate", "M5_information_request_rate", "M6_manual_review_rate",
                "M7F_unsafe_provisional_approvals_fraud", "F1_genuine_but_informal_escalation"):
        lines.append(f"| {key} | " + " | ".join(_fmt(result["metrics_itt"][s][key]) for s in config.SYSTEMS) + " |")
    lines += ["", "## Comparison family: hybrid v3 vs hybrid v2 (case level, cluster sign-flip, Holm)", "",
              "| Comparison | Difference (95% CI) | p | Holm p | Claim |", "|---|---|---|---|---|"]
    for k, v in result["comparisons_hybrid_v3_vs_hybrid_v2"].items():
        lines.append(f"| {k} | {v['difference']} ({v['difference_ci']}) | {v['cluster_sign_flip_p']} | {v['holm_p']} | {v['claim']} |")
    ni = result["fairness_noninferiority"]
    lines += ["", f"Fairness non-inferiority (legitimate-complete approval, margin {ni.get('margin')}): **{ni.get('result')}** "
                  f"(difference {ni.get('difference')}, CI {ni.get('ci')})."]
    t = result["tradeoff"]
    lines += ["", "## Trade-off: fraud prevented vs legitimate applicants delayed", "",
              "| System | Fraud detected | Fraud provisionally approved | Fraud activated (sim.) | Legitimate delayed | Legitimate activated (sim.) |",
              "|---|---|---|---|---|---|"]
    for s in config.SYSTEMS:
        c = t[s]["counts"]
        lines.append(f"| {s} | {c['fraud_detected']}/{c['fraud_cases']} | {c['fraud_provisionally_approved']} | "
                     f"{c['fraud_activated_simulated']} | {c['legitimate_delayed']}/{c['legitimate_cases']} | "
                     f"{c['legitimate_activated_simulated']} |")
    lines += ["", f"hybrid v3 vs hybrid v2: {t['hybrid_v3_vs_hybrid_v2']}", "", f"{t['retrospective_context']}"]
    api = result["api"]
    lines += ["", "## API reliability and latency", "",
              f"Requests sent: {api['requests_sent']}; outcomes: {api['requests_by_outcome']}; retries used: "
              f"{api['retries_used']}; quota pauses: {api['quota_pauses']}; model versions: {api['model_versions']}.", ""]
    return "\n".join(lines) + "\n"
