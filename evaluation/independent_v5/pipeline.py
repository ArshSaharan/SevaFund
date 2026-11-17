"""Run the frozen systems on one case and simulate the confirmation steps (read-only use of frozen code).

Every system gets the same Gemini answer.  Each automated decision starts a record in the frozen approval workflow
(names_institution=True for all systems).  The confirmation step is SIMULATED from the author-written external
environment: it is not real-world verification and is labelled as such in every output.
"""
from datetime import date
from typing import Optional

from app.services.development_approval_workflow import record_confirmation
from app.services.development_approval_workflow.schemas import (ConfirmationCheck, ConfirmationOutcome,
                                                                ConfirmationRecord, ContactSource, WorkflowState)
from app.services.development_gemini_verification import assess_dates as v2_assess_dates
from app.services.development_gemini_verification import combine as v2_combine
from app.services.development_hybrid_v3 import activation_status, combine as v3_combine, start_record, v3_case
from app.services.development_verifier_v3 import verify_case
from app.services.development_verifier_v3.config import DEFAULT_CONFIG

SIMULATED = "SIMULATED from author-written external environment; not real-world verification"
ORDER = (ConfirmationCheck.BENEFICIARY, ConfirmationCheck.INSTITUTION, ConfirmationCheck.PAYMENT_DESTINATION)


def _campaign_text(data: dict) -> str:
    return " ".join([str(data.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state")] +
                    [d.get("content", "") for d in data.get("documents", [])])


def _independent_source(check: ConfirmationCheck, data: dict) -> ContactSource:
    if check == ConfirmationCheck.INSTITUTION:
        organisation = (data.get("beneficiary_type") or "").upper() in {"ORGANISATION", "ORGANIZATION", "NGO"}
        return ContactSource.OFFICIAL_REGISTRY if organisation or "COMMUN" in data["category"].upper() \
            else ContactSource.OFFICIAL_DIRECTORY
    return ContactSource.PLATFORM_KYC


def simulate_confirmation(decision: str, data: dict, environment: dict) -> dict:
    """Pass 1 offers the campaign-supplied contacts (they must never satisfy a check); pass 2 contacts each party
    through an independently sourced channel and records the author-written response."""
    record = start_record(decision, data["category"], data.get("beneficiary_type"), [])
    initial = record.state.value
    text = _campaign_text(data)
    supplied_attempts = 0
    if record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION:
        for check in ORDER:
            supplied = (environment.get(check.value) or {}).get("campaign_supplied_contact")
            if supplied and record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION:
                supplied_attempts += 1
                record_confirmation(record, ConfirmationRecord(
                    check=check, outcome=ConfirmationOutcome(supplied["response"]),
                    contact_source=ContactSource.CAMPAIGN_SUPPLIED, contact_reference="campaign-supplied-contact",
                    verifier_id="simulated-verifier", note="simulated: campaign-supplied contact"), text)
        for check in ORDER:
            if record.state != WorkflowState.ELIGIBLE_PENDING_CONFIRMATION:
                break
            response = (environment.get(check.value) or {}).get("independent_response", "INCONCLUSIVE")
            record_confirmation(record, ConfirmationRecord(
                check=check, outcome=ConfirmationOutcome(response), contact_source=_independent_source(check, data),
                contact_reference=f"independent-{check.value.lower()}", verifier_id="simulated-verifier",
                note="simulated: independently sourced contact"), text)
    status = activation_status(record)
    satisfied = []
    for requirement in record.required_confirmations:
        if requirement.satisfied and requirement.satisfied_by is not None:
            confirmation = record.confirmations[requirement.satisfied_by]
            satisfied.append({"check": requirement.check.value, "source": confirmation.contact_source.value,
                              "outcome": confirmation.outcome.value})
    activations = [t for t in record.history if t.to_state == WorkflowState.VERIFIED_ACTIVE]
    return {"simulation": SIMULATED, "initial_state": initial, "end_state": record.state.value,
            "activated": record.state == WorkflowState.VERIFIED_ACTIVE,
            "activation_allowed": status["activation_allowed"], "authenticity": status["authenticity"],
            "required_checks": status["required_checks"], "pending_checks": status["pending_checks"],
            "satisfied": satisfied, "confirmation_records": len(record.confirmations),
            "campaign_supplied_attempts": supplied_attempts,
            "campaign_supplied_satisfied": sum(s["source"] == ContactSource.CAMPAIGN_SUPPLIED.value for s in satisfied),
            "activation_triggers": [t.trigger for t in activations]}


def simulate_amount_check(goal: float, environment: dict, tolerance: float) -> dict:
    """Appendix A of the protocol, simulated: the cost issuer's own stated figure (minus other payers) against the
    goal.  Pre-registered secondary analysis; not part of the frozen system."""
    cost = environment.get("COST_ISSUER") or {}
    stated, other = cost.get("amount_stated_inr"), cost.get("other_payers_inr") or 0
    response = cost.get("independent_response")
    net = None if stated is None else stated - other
    if response == "CONTRADICTED":
        outcome = "CONTRADICTED"
    elif stated is None or response in ("UNREACHABLE", "INCONCLUSIVE"):
        outcome = "OPEN"
    else:
        outcome = "CONFIRMED" if goal <= net * (1 + tolerance) else "CONTRADICTED"
    end = {"CONFIRMED": "VERIFIED_ACTIVE", "OPEN": "ELIGIBLE_PENDING_CONFIRMATION", "CONTRADICTED": "FLAG_FOR_REVIEW"}
    return {"simulation": SIMULATED, "outcome": outcome, "net_amount_inr": net, "goal_inr": goal,
            "end_state_if_required": end[outcome]}


def run_systems(case: dict, gemini: dict, chunks: list, reference: date, amount_tolerance: float) -> dict:
    data, environment = case["input"], case["external_environment"]
    v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
    hv3 = v3_combine(data, v3, gemini, chunks, reference)
    dates = v2_assess_dates([(d["title"], d.get("content", "")) for d in data.get("documents", [])], reference)
    hv2 = v2_combine(v3.decision.value, gemini, chunks, _campaign_text(data), dates, category=data["category"],
                     beneficiary_type=data.get("beneficiary_type"), v3_information_requests=v3.information_requests)
    systems = {
        "hybrid_v3": {"decision": hv3.decision, "workflow_state": hv3.workflow_state, "triggers": hv3.triggers,
                      "review_basis": hv3.review_basis, "financial_evidence": hv3.financial_evidence.get("status"),
                      "cross_document_findings": [f["code"] for f in hv3.cross_document_findings],
                      "unverified_concerns": len(hv3.unverified_concerns), "authenticity": hv3.authenticity},
        "hybrid_v2": {"decision": hv2.decision, "workflow_state": hv2.workflow_state, "triggers": hv2.triggers,
                      "review_basis": None},
        "v3_alone": {"decision": v3.decision.value, "workflow_state": None, "triggers": sorted({f.code for f in v3.findings}),
                     "review_basis": None},
    }
    for name, result in systems.items():
        confirmation = simulate_confirmation(result["decision"], data, environment)
        result["confirmation_simulated"] = confirmation
        result["workflow_state"] = result["workflow_state"] or confirmation["initial_state"]
        result["amount_check_simulated"] = (simulate_amount_check(data["goal_amount"], environment, amount_tolerance)
                                            if confirmation["activated"] else None)
    return systems


def gemini_summary(outcome: dict) -> dict:
    return {"status": outcome.get("status"), "failure_category": outcome.get("failure_category"),
            "decision": outcome.get("decision"), "risk_level": outcome.get("risk_level"),
            "concerns": len(outcome.get("concerns") or []), "red_flags": len(outcome.get("red_flag_texts") or []),
            "latency_seconds": outcome.get("latency_seconds"), "model": outcome.get("model")}
