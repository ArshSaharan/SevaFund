"""Activation workflow with independent amount confirmation (hybrid v4, development only).

The frozen workflow (app/services/development_approval_workflow, unchanged) activates a campaign once the beneficiary,
the payment destination and the institution are confirmed.  It never confirms the requested amount, so an inflated
goal backed by a consistent but false quotation could activate.  This workflow keeps the frozen states, contact
sources and outcomes, and adds a fourth required check:

  AMOUNT  the cost issuer (hospital billing desk, institution accounts office, supplier), reached through an
          independently sourced contact, states the amount due and any amount already covered by insurance, a
          scheme, a scholarship or an advance.  The goal must not exceed (stated - other payers) by more than the
          tolerance.  A larger goal is a contradiction and goes to manual review.

Rules (each one enforced here and tested):
  * Automated verification never activates.  APPROVED -> ELIGIBLE_PENDING_CONFIRMATION with four required checks.
  * A check is satisfied only by a CONFIRMED outcome through an independent source.  Contacts supplied by the
    campaign - or found in its own text - are recorded but never satisfy a check.
  * Any CONTRADICTED outcome (or an amount above the confirmed need) -> FLAG_FOR_REVIEW.
  * VERIFIED_ACTIVE only through `record_confirmation`, only when all four checks are satisfied.  Disbursement is
    limited to the independently confirmed amount.
  * Reviewers cannot activate.  Clearing a flagged campaign voids earlier confirmations.
  * Fair route for missing quotations: a campaign whose only open item is formal cost evidence can be moved by a
    caseworker to assisted cost confirmation.  The amount is then established by the cost issuer directly - the
    same four checks still apply, so no safeguard is bypassed.
  * Every event is appended to a hash-chained audit log.
"""
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable, List, Optional

from pydantic import BaseModel, Field

from app.services.development_approval_workflow.schemas import (INDEPENDENT_SOURCES, ConfirmationOutcome, ContactSource,
                                                                WorkflowState)
from app.services.development_approval_workflow.workflow import effective_source

from .audit import AuditLog, utcnow
from .config import POLICY_VERSION, SETTINGS

S = WorkflowState
ASSISTED_COST_CONFIRMATION = "ASSISTED_COST_CONFIRMATION"


class Check(str, Enum):
    BENEFICIARY = "BENEFICIARY"
    INSTITUTION = "INSTITUTION"
    PAYMENT_DESTINATION = "PAYMENT_DESTINATION"
    AMOUNT = "AMOUNT"


class Confirmation(BaseModel):
    check: Check
    outcome: ConfirmationOutcome
    contact_source: ContactSource
    contact_reference: str = ""
    verifier_id: str
    note: str = ""
    stated_amount_inr: Optional[float] = None    # AMOUNT: what the cost issuer itself states is due
    other_payers_inr: float = 0                  # AMOUNT: already covered by insurance, a scheme, scholarship, advance


class Requirement(BaseModel):
    check: Check
    description: str
    satisfied: bool = False
    satisfied_by: Optional[int] = None


class Record(BaseModel):
    case_id: str = ""
    state: WorkflowState
    decision: str
    category: str
    beneficiary_type: Optional[str] = None
    goal_amount: float
    manual_route: Optional[str] = None
    requirements: List[Requirement] = Field(default_factory=list)
    confirmations: List[Confirmation] = Field(default_factory=list)
    information_requests: List[str] = Field(default_factory=list)
    confirmed_amount_inr: Optional[float] = None
    disbursement_limit_inr: Optional[float] = None
    activation_trigger: Optional[str] = None
    audit: AuditLog = Field(default_factory=AuditLog)
    policy_version: str = POLICY_VERSION

    @property
    def pending_checks(self) -> List[Check]:
        return [r.check for r in self.requirements if not r.satisfied]

    @property
    def disbursement_allowed(self) -> bool:
        return self.state == S.VERIFIED_ACTIVE


class IllegalTransition(ValueError):
    pass


ALLOWED = {
    None: {S.ELIGIBLE_PENDING_CONFIRMATION, S.NEEDS_MORE_INFORMATION, S.FLAG_FOR_REVIEW, S.REJECTED, S.VERIFICATION_ERROR},
    S.ELIGIBLE_PENDING_CONFIRMATION: {S.VERIFIED_ACTIVE, S.FLAG_FOR_REVIEW},
    S.NEEDS_MORE_INFORMATION: {S.ELIGIBLE_PENDING_CONFIRMATION, S.FLAG_FOR_REVIEW},
    S.FLAG_FOR_REVIEW: {S.ELIGIBLE_PENDING_CONFIRMATION, S.NEEDS_MORE_INFORMATION, S.REJECTED},
    S.VERIFICATION_ERROR: set(),            # re-run automated verification instead (a new record)
    S.VERIFIED_ACTIVE: {S.FLAG_FOR_REVIEW},
    S.REJECTED: set(),
}
DECISION_TO_STATE = {"APPROVED": S.ELIGIBLE_PENDING_CONFIRMATION, "NEEDS_MORE_INFORMATION": S.NEEDS_MORE_INFORMATION,
                     "FLAG_FOR_REVIEW": S.FLAG_FOR_REVIEW, "REJECTED": S.REJECTED,
                     "VERIFICATION_ERROR": S.VERIFICATION_ERROR}


def requirements_for(category: str, beneficiary_type: Optional[str], assisted: bool = False) -> List[Requirement]:
    category = (category or "").upper()
    organisation = (beneficiary_type or "").upper() in {"ORGANISATION", "ORGANIZATION", "NGO"}
    if "MEDIC" in category:
        institution, issuer = "Treating hospital confirms the patient and the treatment.", "hospital billing desk"
    elif "EDUC" in category:
        institution, issuer = "Educational institution confirms enrolment and the fee demand.", "institution's accounts office"
    else:
        institution = "Registering authority confirms the organisation's registration is current."
        issuer = "supplier or contractor"
    amount = (f"The {issuer}, contacted independently, states the amount due and anything already covered; the goal "
              f"may not exceed the confirmed need by more than {SETTINGS['amount_confirmation_tolerance']:.0%}.")
    if assisted:
        amount += " (Assisted route: this independent statement replaces the missing formal quotation.)"
    return [
        Requirement(check=Check.BENEFICIARY, description=("Organisation's legal identity and authorised signatory verified."
                                                          if organisation else "Beneficiary's identity verified.")),
        Requirement(check=Check.INSTITUTION, description=institution),
        Requirement(check=Check.PAYMENT_DESTINATION,
                    description="Payout account verified as belonging to the institution, supplier or verified beneficiary."),
        Requirement(check=Check.AMOUNT, description=amount),
    ]


def _move(record: Record, to_state: WorkflowState, actor: str, trigger: str, reason: str,
          clock: Optional[Callable[[], datetime]] = None, **data) -> Record:
    started = any(e.event == "STATE_CHANGE" for e in record.audit.entries)
    if to_state not in ALLOWED[record.state if started else None]:
        raise IllegalTransition(f"{record.state.value if started else 'NEW'} -> {to_state.value} is not allowed")
    if to_state == S.VERIFIED_ACTIVE and (record.pending_checks or trigger != "confirmation"
                                          or {r.check for r in record.requirements} != set(Check)):
        raise IllegalTransition("VERIFIED_ACTIVE requires all four independent confirmations")
    record.audit.append(actor, "STATE_CHANGE", {"from": record.state.value if started else None, "to": to_state.value,
                                                "trigger": trigger, "reason": reason, **data}, clock)
    record.state = to_state
    return record


def start(decision: str, case: dict, information_requests: Iterable[str] = (), manual_route: Optional[str] = None,
          explanation: Optional[dict] = None, case_id: str = "", clock: Optional[Callable[[], datetime]] = None) -> Record:
    """Initial record for an automated decision.  Never VERIFIED_ACTIVE."""
    state = DECISION_TO_STATE.get(decision, S.VERIFICATION_ERROR)
    record = Record(case_id=case_id, state=state, decision=decision, category=case.get("category", ""),
                    beneficiary_type=case.get("beneficiary_type"), goal_amount=float(case.get("goal_amount") or 0),
                    manual_route=manual_route if state == S.NEEDS_MORE_INFORMATION else None,
                    information_requests=list(information_requests) if state == S.NEEDS_MORE_INFORMATION else [])
    if state == S.ELIGIBLE_PENDING_CONFIRMATION:
        record.requirements = requirements_for(record.category, record.beneficiary_type)
    record.audit.append("automated_verification", "AUTOMATED_DECISION",
                        {"decision": decision, "explanation": explanation or {}, "policy_version": POLICY_VERSION}, clock)
    reasons = {
        S.ELIGIBLE_PENDING_CONFIRMATION: "Provisional approval only: no funds can be raised or released until the "
                                         "beneficiary, institution, payment destination and amount are independently confirmed.",
        S.NEEDS_MORE_INFORMATION: "Evidence is incomplete; specific requests were sent. This is not a fraud finding.",
        S.FLAG_FOR_REVIEW: "A reviewer must examine the findings before anything else happens.",
        S.REJECTED: "Multiple independent deterministic contradictions.",
        S.VERIFICATION_ERROR: "Automated verification did not complete; it must be re-run. Never an approval.",
    }
    return _move(record, state, "automated_verification", "automated_verification", reasons[state], clock,
                 required_checks=[r.check.value for r in record.requirements],
                 information_requests=record.information_requests, manual_route=record.manual_route)


def record_confirmation(record: Record, confirmation: Confirmation, campaign_text: str = "",
                        clock: Optional[Callable[[], datetime]] = None) -> Record:
    if record.state != S.ELIGIBLE_PENDING_CONFIRMATION:
        raise IllegalTransition(f"Confirmations apply only to pending campaigns, not {record.state.value}")
    source = effective_source(confirmation, campaign_text)          # frozen rule, reused unchanged
    confirmation = confirmation.model_copy(update={"contact_source": source})
    record.confirmations.append(confirmation)
    index = len(record.confirmations) - 1
    record.audit.append(confirmation.verifier_id, "CONFIRMATION_ATTEMPT",
                        {"check": confirmation.check.value, "outcome": confirmation.outcome.value,
                         "contact_source": source.value, "independent": source in INDEPENDENT_SOURCES,
                         "stated_amount_inr": confirmation.stated_amount_inr,
                         "other_payers_inr": confirmation.other_payers_inr, "note": confirmation.note}, clock)
    check = confirmation.check.value
    if confirmation.outcome == ConfirmationOutcome.CONTRADICTED:
        return _move(record, S.FLAG_FOR_REVIEW, confirmation.verifier_id, "confirmation",
                     f"{check}: an independent party contradicted a material fact; manual review required.", clock)
    if confirmation.outcome != ConfirmationOutcome.CONFIRMED or source not in INDEPENDENT_SOURCES:
        return record                                               # open; recorded in the audit log
    requirement = next((r for r in record.requirements if r.check == confirmation.check), None)
    if requirement is None or requirement.satisfied:
        return record
    if confirmation.check == Check.AMOUNT:
        if confirmation.stated_amount_inr is None:
            return record                                           # issuer did not state a figure: still open
        net = confirmation.stated_amount_inr - (confirmation.other_payers_inr or 0)
        limit = net * (1 + SETTINGS["amount_confirmation_tolerance"])
        if record.goal_amount > limit:
            excess = record.goal_amount / net - 1 if net > 0 else float("inf")
            return _move(record, S.FLAG_FOR_REVIEW, confirmation.verifier_id, "confirmation",
                         f"AMOUNT: the goal of Rs {record.goal_amount:,.0f} exceeds the independently confirmed need of "
                         f"Rs {net:,.0f} ({'no remaining need' if net <= 0 else f'+{excess:.0%}'}); manual review required.",
                         clock, confirmed_need_inr=net)
        record.confirmed_amount_inr = net
    requirement.satisfied, requirement.satisfied_by = True, index
    if record.pending_checks:
        return record
    record.disbursement_limit_inr = min(record.goal_amount, record.confirmed_amount_inr)
    record.activation_trigger = "confirmation"
    return _move(record, S.VERIFIED_ACTIVE, confirmation.verifier_id, "confirmation",
                 "All four checks independently confirmed; disbursement allowed up to the confirmed amount.", clock,
                 disbursement_limit_inr=record.disbursement_limit_inr)


def assisted_cost_review(record: Record, caseworker_id: str, reason: str,
                         clock: Optional[Callable[[], datetime]] = None) -> Record:
    """Fair route for genuine applicants without a formal quotation.  Allowed only when automated verification found
    nothing but missing cost evidence.  Leads to the same four independent checks; it never activates by itself."""
    if record.state != S.NEEDS_MORE_INFORMATION or record.manual_route != ASSISTED_COST_CONFIRMATION:
        raise IllegalTransition("Assisted cost review applies only to campaigns whose sole open item is cost evidence")
    record.requirements = requirements_for(record.category, record.beneficiary_type, assisted=True)
    return _move(record, S.ELIGIBLE_PENDING_CONFIRMATION, caseworker_id, "assisted_cost_review", reason, clock,
                 required_checks=[r.check.value for r in record.requirements])


def reviewer_resolution(record: Record, to_state: WorkflowState, reviewer_id: str, reason: str,
                        clock: Optional[Callable[[], datetime]] = None) -> Record:
    """A reviewer resolves a flagged campaign.  Reviewers cannot activate; a cleared campaign repeats every check."""
    if record.state != S.FLAG_FOR_REVIEW:
        raise IllegalTransition("Reviewer resolution applies only to FLAG_FOR_REVIEW")
    if to_state == S.VERIFIED_ACTIVE:
        raise IllegalTransition("Reviewers cannot activate a campaign")
    if to_state == S.ELIGIBLE_PENDING_CONFIRMATION:
        record.requirements = requirements_for(record.category, record.beneficiary_type)
        record.confirmed_amount_inr = None
    return _move(record, to_state, reviewer_id, "reviewer", reason, clock)


def suspend(record: Record, actor: str, reason: str, clock: Optional[Callable[[], datetime]] = None) -> Record:
    return _move(record, S.FLAG_FOR_REVIEW, actor, "reviewer", reason, clock)


def activation_status(record: Record) -> dict:
    """Independent re-check of the record: activation is valid only if all four checks were satisfied by CONFIRMED
    outcomes from independent sources, the amount is within tolerance, and the audit chain is intact."""
    satisfied = {}
    for requirement in record.requirements:
        if requirement.satisfied and requirement.satisfied_by is not None:
            c = record.confirmations[requirement.satisfied_by]
            satisfied[requirement.check.value] = (c.outcome == ConfirmationOutcome.CONFIRMED
                                                  and c.contact_source in INDEPENDENT_SOURCES)
    all_independent = set(satisfied) == {c.value for c in Check} and all(satisfied.values())
    amount_ok = (record.confirmed_amount_inr is not None and record.goal_amount <=
                 record.confirmed_amount_inr * (1 + SETTINGS["amount_confirmation_tolerance"]))
    active = record.state == S.VERIFIED_ACTIVE
    valid = active and all_independent and amount_ok and record.activation_trigger == "confirmation" and record.audit.verify()
    return {"state": record.state.value, "activated": active, "activation_valid": valid,
            "disbursement_allowed": record.disbursement_allowed and valid,
            "disbursement_limit_inr": record.disbursement_limit_inr,
            "independently_confirmed": sorted(k for k, v in satisfied.items() if v),
            "pending_checks": [c.value for c in record.pending_checks],
            "audit_entries": len(record.audit.entries), "audit_chain_valid": record.audit.verify(),
            "authenticity": "CONFIRMED_BY_INDEPENDENT_SOURCES" if valid else "UNCONFIRMED"}
