"""Final offline evaluation: frozen V3, hybrid v2, hybrid v3 and hybrid v4 on 60 developer-designed scenarios.

DEVELOPER-DESIGNED SYNTHETIC EVALUATION - NOT INDEPENDENT VALIDATION.

  * Same inputs and the same scripted Gemini answer for every system: each scripted response is passed through the
    frozen hybrid-v2 client (parsing and validation) by a scripted transport.  No network, no API key, no API call;
    a socket guard fails the run if any connection is attempted.
  * Retrieval: production's own no-embedding fallback (evaluation/independent_v5/retrieval.py), unchanged.
  * Confirmation is SIMULATED from each scenario's external environment.  Frozen V3, hybrid v2 and hybrid v3 use the
    frozen workflow (three checks); hybrid v4 uses its own workflow (four checks, including AMOUNT) and, for cases it
    marks ASSISTED_COST_CONFIRMATION, a simulated caseworker takes the assisted route.  Simulated confirmations show
    how the workflow logic behaves; they do not show that real-world verification works.

    python evaluation/final_evaluation/run_final_evaluation.py      # writes evaluation/final_evaluation/results/
"""
import asyncio
import csv
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from app.services.development_approval_workflow.schemas import ConfirmationOutcome, ContactSource  # noqa: E402
from app.services.development_gemini_verification import assess_dates as v2_assess_dates  # noqa: E402
from app.services.development_gemini_verification import combine as v2_combine  # noqa: E402
from app.services.development_gemini_verification import verify_with_gemini  # noqa: E402
from app.services.development_hybrid_v3 import combine as hybrid_v3_combine, v3_case  # noqa: E402
from app.services.development_hybrid_v4 import (ASSISTED_COST_CONFIRMATION, Check, Confirmation,  # noqa: E402
                                                activation_status, assisted_cost_review, decide as hybrid_v4_decide,
                                                record_confirmation, start as v4_start)
from app.services.development_hybrid_v4 import POLICY_VERSION as V4_POLICY, digest as v4_digest  # noqa: E402
from app.services.gemini_api import GeminiAPIError  # noqa: E402
from app.services.development_verifier_v3 import verify_case  # noqa: E402
from app.services.development_verifier_v3.config import DEFAULT_CONFIG  # noqa: E402
from independent_v5 import pipeline, retrieval  # noqa: E402
from independent_v5.preseal import NetworkGuard  # noqa: E402
from independent_v5.stats import wilson  # noqa: E402

HERE = Path(__file__).resolve().parent
SCENARIOS = HERE / "scenarios.jsonl"
RESULTS = HERE / "results"
SYSTEMS = ("v3_frozen", "hybrid_v2", "hybrid_v3", "hybrid_v4")
DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}
MODEL = "gemini-3.6-flash"
LABEL = ("DEVELOPER-DESIGNED SYNTHETIC EVALUATION - NOT INDEPENDENT VALIDATION. Gemini responses are scripted; "
         "external confirmations are simulated and do not show that real-world verification works.")


# ------------------------------------------------------------------ scripted Gemini (through the frozen client)
def _body(recommendation: str, concerns: List[dict], missing: Optional[List[str]] = None) -> dict:
    approve = recommendation == "AUTO_APPROVE"
    return {"authenticity_score": 72 if approve else 45,
            "risk_level": "LOW" if approve else "HIGH" if recommendation in ("FLAG_FOR_REVIEW", "REJECT") else "MEDIUM",
            "recommendation": recommendation, "summary": "Scripted offline response (not a model output).",
            "dimension_scores": {"plausibility": 70, "specificity": 70, "red_flag_score": 70, "documentation": 70},
            "red_flags": [], "positive_signals": [], "missing_requirements": missing or [], "concerns": concerns}


class ScriptedTransport:
    def __init__(self, script: dict):
        self.script, self.calls = script, 0

    async def __call__(self, url, api_key, payload, stage, timeout, max_attempts=1):
        self.calls += 1
        g = self.script
        kind = g["kind"]
        finish = "STOP"
        if kind == "failure" and g["category"] not in ("invalid_json", "truncated"):
            status = {"SERVER_ERROR": 503, "QUOTA_EXHAUSTED": 429}.get(g["category"])
            raise GeminiAPIError(stage, g["category"], status)
        if kind == "approve" or (kind == "failure" and g["category"] == "truncated"):
            body = _body("AUTO_APPROVE", [])
            finish = "MAX_TOKENS" if kind == "failure" else "STOP"
        elif kind == "nmi":
            body = _body("NEEDS_MORE_INFO", [{"category": "MISSING_INFORMATION", "description": m} for m in g["missing"]],
                         g["missing"])
        elif kind == "flag":
            body = _body("FLAG_FOR_REVIEW", [{"category": g["category"], "description": g["description"],
                                              "document_title": g["document"], "evidence_quote": g["quote"]}])
        elif kind == "flag_unquoted":
            body = _body(g.get("recommendation", "FLAG_FOR_REVIEW"),
                         [{"category": "SUSPECTED_FRAUD", "description": g["description"]}])
        else:
            body = None
        text = "{not valid json" if body is None else json.dumps(body)
        return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}],
                "modelVersion": "scripted-offline", "usageMetadata": {}}


# ------------------------------------------------------------------ hybrid v4 workflow simulation
ORDER = (Check.BENEFICIARY, Check.INSTITUTION, Check.PAYMENT_DESTINATION, Check.AMOUNT)


def _party(check: Check) -> str:
    return "COST_ISSUER" if check == Check.AMOUNT else check.value


def _source(check: Check, data: dict) -> ContactSource:
    if check in (Check.INSTITUTION, Check.AMOUNT):
        organisation = (data.get("beneficiary_type") or "").upper() in {"ORGANISATION", "ORGANIZATION", "NGO"}
        return ContactSource.OFFICIAL_REGISTRY if check == Check.INSTITUTION and organisation else ContactSource.OFFICIAL_DIRECTORY
    return ContactSource.PLATFORM_KYC


def simulate_v4(decision, case_id: str, data: dict, environment: dict) -> dict:
    tick = {"n": 0}
    base = datetime.combine(date.fromisoformat(data["submitted_on"]), datetime.min.time(), tzinfo=timezone.utc)

    def clock():
        tick["n"] += 1
        return base + timedelta(minutes=tick["n"])

    text = pipeline._campaign_text(data)
    record = v4_start(decision.decision, data, decision.information_requests, decision.manual_route,
                      decision.audit_payload(), case_id, clock)
    initial = record.state.value
    assisted = False
    if record.manual_route == ASSISTED_COST_CONFIRMATION and record.state.value == "NEEDS_MORE_INFORMATION":
        assisted_cost_review(record, "simulated-caseworker", "Applicant has no formal quotation; amount to be obtained "
                             "from the cost issuer through an independent contact.", clock)
        assisted = True
    supplied_attempts = 0
    if record.state.value == "ELIGIBLE_PENDING_CONFIRMATION":
        for check in ORDER:
            supplied = (environment.get(_party(check)) or {}).get("campaign_supplied_contact")
            if supplied and record.state.value == "ELIGIBLE_PENDING_CONFIRMATION":
                supplied_attempts += 1
                cost = environment.get("COST_ISSUER") or {}
                record_confirmation(record, Confirmation(
                    check=check, outcome=ConfirmationOutcome(supplied["response"]),
                    contact_source=ContactSource.CAMPAIGN_SUPPLIED, contact_reference="campaign-supplied-contact",
                    verifier_id="simulated-verifier", note="simulated: campaign-supplied contact",
                    stated_amount_inr=cost.get("amount_stated_inr") if check == Check.AMOUNT else None), text, clock)
        for check in ORDER:
            if record.state.value != "ELIGIBLE_PENDING_CONFIRMATION":
                break
            party = environment.get(_party(check)) or {}
            record_confirmation(record, Confirmation(
                check=check, outcome=ConfirmationOutcome(party.get("independent_response", "INCONCLUSIVE")),
                contact_source=_source(check, data), contact_reference=f"independent-{check.value.lower()}",
                verifier_id="simulated-verifier", note="simulated: independently sourced contact",
                stated_amount_inr=party.get("amount_stated_inr") if check == Check.AMOUNT else None,
                other_payers_inr=(party.get("other_payers_inr") or 0) if check == Check.AMOUNT else 0), text, clock)
    status = activation_status(record)
    return {"simulation": pipeline.SIMULATED, "initial_state": initial, "end_state": record.state.value,
            "assisted_route_taken": assisted, "activated": status["activated"],
            "activation_valid": status["activation_valid"],
            "amount_independently_confirmed": "AMOUNT" in status["independently_confirmed"],
            "independently_confirmed": status["independently_confirmed"], "pending_checks": status["pending_checks"],
            "campaign_supplied_attempts": supplied_attempts,
            "disbursement_limit_inr": status["disbursement_limit_inr"], "audit_entries": status["audit_entries"],
            "audit_chain_valid": status["audit_chain_valid"], "audit_head": record.audit.head}


def simulate_frozen(decision: str, data: dict, environment: dict) -> dict:
    sim = pipeline.simulate_confirmation(decision, data, environment)
    return {"simulation": sim["simulation"], "initial_state": sim["initial_state"], "end_state": sim["end_state"],
            "assisted_route_taken": False, "activated": sim["activated"], "activation_valid": sim["activation_allowed"],
            "amount_independently_confirmed": False, "independently_confirmed": [s["check"] for s in sim["satisfied"]],
            "pending_checks": sim["pending_checks"], "campaign_supplied_attempts": sim["campaign_supplied_attempts"],
            "disbursement_limit_inr": None, "audit_entries": None, "audit_chain_valid": None, "audit_head": None}


# ------------------------------------------------------------------ one scenario
async def run_one(s: dict) -> dict:
    data, environment = s["input"], s["external_environment"]
    reference = date.fromisoformat(data["submitted_on"])
    chunks, coverage = await retrieval.retrieve(data)
    transport = ScriptedTransport(s["gemini_script"])
    gemini = (await verify_with_gemini(data, chunks, reference, submitted_on=reference, transport=transport,
                                       api_key="offline-scripted-not-a-key", model=MODEL, max_attempts=1)).model_dump()
    v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
    dates = v2_assess_dates([(d["title"], d.get("content", "")) for d in data.get("documents", [])], reference)
    hv2 = v2_combine(v3.decision.value, gemini, chunks, pipeline._campaign_text(data), dates, category=data["category"],
                     beneficiary_type=data.get("beneficiary_type"), v3_information_requests=v3.information_requests)
    hv3 = hybrid_v3_combine(data, v3, gemini, chunks, reference)
    hv4 = hybrid_v4_decide(data, v3, gemini, chunks, reference)

    v3_evidence = sorted({v.document for f in v3.findings for v in f.values if v.document})
    systems = {
        "v3_frozen": {"decision": v3.decision.value, "triggers": sorted({f.code for f in v3.findings}),
                      "reasons": list(v3.reasons), "review_basis": None,
                      "evidence_documents": v3_evidence if v3.decision.value in DETECT else []},
        "hybrid_v2": {"decision": hv2.decision, "triggers": hv2.triggers, "reasons": hv2.reasons, "review_basis": None,
                      "evidence_documents": []},
        "hybrid_v3": {"decision": hv3.decision, "triggers": hv3.triggers, "reasons": hv3.reasons,
                      "review_basis": hv3.review_basis,
                      "evidence_documents": sorted({v for f in hv3.cross_document_findings for v in f.get("values", [])})
                      if hv3.decision in DETECT else []},
        "hybrid_v4": {"decision": hv4.decision, "triggers": hv4.triggers, "reasons": hv4.reasons,
                      "review_basis": hv4.review_basis, "manual_route": hv4.manual_route,
                      "findings": [f.model_dump() for f in hv4.findings], "explanation": hv4.explanation,
                      "evidence_documents": sorted({e.get("document") or e.get("quote") for f in hv4.findings
                                                    for e in f.evidence if e.get("document") or e.get("quote")})
                      if hv4.decision in DETECT else []},
    }
    for name, result in systems.items():
        result["confirmation"] = (simulate_v4(hv4, s["case_id"], data, environment) if name == "hybrid_v4"
                                  else simulate_frozen(result["decision"], data, environment))
    return {"case_id": s["case_id"], "stratum": s["stratum"], "truth_label": s["truth_label"],
            "documentation": s["documentation"], "category": s["category"], "mechanism": s["mechanism"],
            "incomplete_subtype": s["incomplete_subtype"], "reference_date": reference.isoformat(),
            "retrieval": coverage, "gemini": {"script": s["gemini_script"]["kind"], "status": gemini["status"],
                                              "failure_category": gemini["failure_category"],
                                              "decision": gemini["decision"], "requests": transport.calls},
            "systems": systems}


# ------------------------------------------------------------------ metrics
def rate(rows: List[dict], hit) -> dict:
    n, k = len(rows), sum(1 for r in rows if hit(r))
    ci = wilson(k, n) if n else None
    return {"count": k, "n": n, "percent": round(100 * k / n, 1) if n else None,
            "wilson95": [round(100 * ci[0], 1), round(100 * ci[1], 1)] if ci else None}


def system_metrics(rows: List[dict], name: str) -> dict:
    def sys_(r):
        return r["systems"][name]

    def dec(r):
        return sys_(r)["decision"]

    def act(r):
        return sys_(r)["confirmation"]["activated"]

    by = {k: [r for r in rows if r["stratum"] == k] for k in ("FD", "FS", "LC", "LI", "BC")}
    fraud, legit = by["FD"] + by["FS"], by["LC"] + by["LI"]
    detections = [r for r in rows if dec(r) in DETECT]
    activations = [r for r in rows if act(r)]
    confirmation_reviews = [r for r in rows if sys_(r)["confirmation"]["initial_state"] != "FLAG_FOR_REVIEW"
                            and sys_(r)["confirmation"]["end_state"] == "FLAG_FOR_REVIEW"]
    return {
        "decisions_by_stratum": {k: {d: sum(dec(r) == d for r in v) for d in
                                     ("APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR")}
                                 for k, v in by.items()},
        "fraud_detected_all": rate(fraud, lambda r: dec(r) in DETECT),
        "fraud_detected_detectable": rate(by["FD"], lambda r: dec(r) in DETECT),
        "fraud_detected_sophisticated": rate(by["FS"], lambda r: dec(r) in DETECT),
        "fraud_provisionally_approved": rate(fraud, lambda r: dec(r) == "APPROVED"),
        "incomplete_provisionally_approved": rate(by["LI"], lambda r: dec(r) == "APPROVED"),
        "borderline_provisionally_approved": rate(by["BC"], lambda r: dec(r) == "APPROVED"),
        "fraud_activated_simulated": rate(fraud, act),
        "fraud_held_before_activation_simulated": rate(fraud, lambda r: not act(r)),
        "borderline_activated_simulated": rate(by["BC"], act),
        "activations_without_independent_amount_confirmation": rate(
            activations, lambda r: not sys_(r)["confirmation"]["amount_independently_confirmed"]),
        "activations_failing_activation_recheck": rate(activations, lambda r: not sys_(r)["confirmation"]["activation_valid"]),
        "false_positives_all_legitimate": rate(legit, lambda r: dec(r) in DETECT),
        "false_positives_complete": rate(by["LC"], lambda r: dec(r) in DETECT),
        "false_positives_incomplete": rate(by["LI"], lambda r: dec(r) in DETECT),
        "legitimate_complete_approved": rate(by["LC"], lambda r: dec(r) == "APPROVED"),
        "legitimate_complete_activated_simulated": rate(by["LC"], act),
        "legitimate_incomplete_activated_simulated": rate(by["LI"], act),
        "genuine_but_informal_activated_simulated": rate([r for r in by["LI"] if r["incomplete_subtype"] == "genuine_but_informal"], act),
        "information_requests_all": rate(rows, lambda r: dec(r) == "NEEDS_MORE_INFORMATION"),
        "information_requests_legitimate_complete": rate(by["LC"], lambda r: dec(r) == "NEEDS_MORE_INFORMATION"),
        "information_requests_legitimate_incomplete": rate(by["LI"], lambda r: dec(r) == "NEEDS_MORE_INFORMATION"),
        "manual_reviews_automated": rate(rows, lambda r: dec(r) == "FLAG_FOR_REVIEW"),
        "manual_reviews_at_confirmation_simulated": {"count": len(confirmation_reviews),
                                                     "cases": [r["case_id"] for r in confirmation_reviews]},
        "rejections": rate(rows, lambda r: dec(r) == "REJECTED"),
        "rejections_without_v3_rejection": rate(rows, lambda r: dec(r) == "REJECTED"
                                                and r["systems"]["v3_frozen"]["decision"] != "REJECTED"),
        "verification_failures": rate(rows, lambda r: dec(r) == "VERIFICATION_ERROR"),
        "assisted_route_taken": rate(rows, lambda r: sys_(r)["confirmation"]["assisted_route_taken"]),
        "explanations": {
            "decisions_with_reason": rate(rows, lambda r: bool(sys_(r)["reasons"])),
            "detections_with_review_basis": rate(detections, lambda r: bool(sys_(r)["review_basis"])),
            "detections_with_document_evidence": rate(detections, lambda r: bool(sys_(r)["evidence_documents"])),
            "tamper_evident_audit_log": rate(rows, lambda r: bool(sys_(r)["confirmation"]["audit_chain_valid"])),
        },
        "fraud_activated_cases": [r["case_id"] for r in fraud if act(r)],
        "fraud_missed_cases": [r["case_id"] for r in fraud if dec(r) not in DETECT],
        "false_positive_cases": [r["case_id"] for r in legit if dec(r) in DETECT],
    }


def write_outputs(rows: List[dict], metrics: dict, meta: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "case_level.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                                                      for r in rows), encoding="utf-8")
    (RESULTS / "metrics.json").write_text(json.dumps({"meta": meta, "metrics": metrics}, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    with (RESULTS / "case_level.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "stratum", "truth", "gemini_script", "gemini_status"] +
                        [f"{s}_{k}" for s in SYSTEMS for k in ("decision", "end_state", "activated")])
        for r in rows:
            writer.writerow([r["case_id"], r["stratum"], r["truth_label"], r["gemini"]["script"], r["gemini"]["status"]] +
                            [x for s in SYSTEMS for x in (r["systems"][s]["decision"],
                                                          r["systems"][s]["confirmation"]["end_state"],
                                                          r["systems"][s]["confirmation"]["activated"])])


def main() -> dict:
    scenarios = [json.loads(line) for line in SCENARIOS.read_text(encoding="utf-8").splitlines() if line.strip()]
    with NetworkGuard() as guard:
        rows = [asyncio.run(run_one(s)) for s in scenarios]
    if guard.attempts:
        raise SystemExit(f"network access attempted: {guard.attempts}")
    metrics = {name: system_metrics(rows, name) for name in SYSTEMS}
    meta = {"label": LABEL, "scenarios": len(rows), "scenarios_sha256": __import__("hashlib").sha256(
                SCENARIOS.read_bytes()).hexdigest(),
            "strata": {k: sum(r["stratum"] == k for r in rows) for k in ("FD", "FS", "LC", "LI", "BC")},
            "gemini_script": {k: sum(r["gemini"]["script"] == k for r in rows) for k in
                              sorted({r["gemini"]["script"] for r in rows})},
            "gemini_failures": sum(r["gemini"]["status"] != "OK" for r in rows),
            "network_connections_attempted": len(guard.attempts), "api_calls": 0,
            "hybrid_v4_policy": V4_POLICY, "hybrid_v4_settings_digest": v4_digest(),
            "systems": {"v3_frozen": "frozen V3 (development_verifier_v3) alone; frozen workflow",
                        "hybrid_v2": "frozen hybrid v2 (development_gemini_verification); frozen workflow",
                        "hybrid_v3": "frozen hybrid v3 (development_hybrid_v3); frozen workflow",
                        "hybrid_v4": "hybrid v4 (development_hybrid_v4); four-check workflow with assisted route"}}
    write_outputs(rows, metrics, meta)
    return {"meta": meta, "metrics": metrics}


if __name__ == "__main__":
    out = main()
    for name in SYSTEMS:
        m = out["metrics"][name]
        print(name, {k: (v["count"], v["n"]) for k, v in m.items() if isinstance(v, dict) and "count" in v and "n" in v})
