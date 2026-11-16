"""Development-only approval workflow: ELIGIBLE_PENDING_EXTERNAL_VERIFICATION.

Policy (decided 2026-11-16):

* Automated verification never activates a campaign.  An automated APPROVED
  becomes ELIGIBLE_PENDING_CONFIRMATION, with external confirmations required for
  the beneficiary, the payment destination and the relevant hospital,
  educational institution or registering authority.
* A confirmation counts only if it was obtained through independently
  established contact details (registry, official directory, platform KYC, a
  previously verified record).  Contact details supplied by the campaign creator
  - or found in the campaign's own uploads - are recorded but never sufficient.
* An external party contradicting a material fact sends the campaign to
  FLAG_FOR_REVIEW.  Unreachable / inconclusive contacts leave it pending.
* Unresolved material contradictions -> FLAG_FOR_REVIEW; missing essential
  information -> NEEDS_MORE_INFORMATION with targeted requests; verification
  errors -> VERIFICATION_ERROR (never an approval).
* Disbursement is allowed only in VERIFIED_ACTIVE.

Every state change is appended to `history`; transitions outside the table
raise `IllegalTransition`.
"""
import re
from typing import Iterable, Optional

from .schemas import (
    INDEPENDENT_SOURCES, AutomatedOutcome, ConfirmationCheck, ConfirmationOutcome, ConfirmationRecord, ContactSource,
    RequiredConfirmation, Transition, WorkflowRecord, WorkflowState,
)

S = WorkflowState
ALLOWED = {
    # from automated verification (no prior state)
    None: {S.ELIGIBLE_PENDING_CONFIRMATION, S.NEEDS_MORE_INFORMATION, S.FLAG_FOR_REVIEW, S.REJECTED,
           S.VERIFICATION_ERROR},
    S.ELIGIBLE_PENDING_CONFIRMATION: {S.VERIFIED_ACTIVE, S.FLAG_FOR_REVIEW, S.ELIGIBLE_PENDING_CONFIRMATION},
    # re-verification after the campaigner responds
    S.NEEDS_MORE_INFORMATION: {S.ELIGIBLE_PENDING_CONFIRMATION, S.NEEDS_MORE_INFORMATION, S.FLAG_FOR_REVIEW,
                               S.REJECTED, S.VERIFICATION_ERROR},
    # a human reviewer resolves the contradiction one way or the other
    S.FLAG_FOR_REVIEW: {S.ELIGIBLE_PENDING_CONFIRMATION, S.NEEDS_MORE_INFORMATION, S.REJECTED},
    # a system failure can only be retried, never approved
    S.VERIFICATION_ERROR: {S.ELIGIBLE_PENDING_CONFIRMATION, S.NEEDS_MORE_INFORMATION, S.FLAG_FOR_REVIEW,
                           S.REJECTED, S.VERIFICATION_ERROR},
    # an active campaign can be suspended if new evidence appears
    S.VERIFIED_ACTIVE: {S.FLAG_FOR_REVIEW},
    S.REJECTED: set(),
}
AUTOMATED_TO_STATE = {
    "APPROVED": S.ELIGIBLE_PENDING_CONFIRMATION,
    "NEEDS_MORE_INFORMATION": S.NEEDS_MORE_INFORMATION,
    "FLAG_FOR_REVIEW": S.FLAG_FOR_REVIEW,
    "REJECTED": S.REJECTED,
    "VERIFICATION_ERROR": S.VERIFICATION_ERROR,
}
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d \-()]{6,}\d")


class IllegalTransition(ValueError):
    pass


def _move(record: WorkflowRecord, to_state: WorkflowState, trigger: str, actor: str, reason: str) -> WorkflowRecord:
    if to_state not in ALLOWED[record.state if record.history else None]:
        raise IllegalTransition(f"{record.state.value if record.history else 'NEW'} -> {to_state.value} is not allowed")
    if to_state == S.VERIFIED_ACTIVE and (record.pending_checks or trigger != "confirmation"):
        raise IllegalTransition("VERIFIED_ACTIVE requires every required confirmation to be satisfied")
    record.history.append(Transition(from_state=record.state if record.history else None, to_state=to_state,
                                     trigger=trigger, actor=actor, reason=reason))
    record.state = to_state
    record.reasons.append(reason)
    return record


def required_checks(outcome: AutomatedOutcome) -> list:
    """Which external confirmations a pending campaign needs, by category."""
    category = (outcome.category or "").upper()
    organisation = (outcome.beneficiary_type or "").upper() in {"ORGANISATION", "ORGANIZATION", "NGO"}
    if "MEDIC" in category:
        institution = "Treating hospital confirms the patient, the treatment and the billed amount."
    elif "EDUC" in category:
        institution = "Educational institution confirms enrolment, the fee demand and its payee account."
    elif organisation or "COMMUN" in category:
        institution = "Registering authority confirms the organisation's registration is current."
    else:
        institution = "The institution named by the campaign confirms the claimed need."
    checks = [
        RequiredConfirmation(check=ConfirmationCheck.BENEFICIARY,
                             description=("Organisation's legal identity and authorised signatory verified."
                                          if organisation else "Beneficiary's identity verified (platform KYC "
                                          "or the institution's own records).")),
        RequiredConfirmation(check=ConfirmationCheck.PAYMENT_DESTINATION,
                             description="Payout account verified as belonging to the institution, supplier "
                                         "or the verified beneficiary (bank account-holder name match)."),
    ]
    if outcome.names_institution or organisation:
        checks.append(RequiredConfirmation(check=ConfirmationCheck.INSTITUTION, description=institution))
    return checks


def start(outcome: AutomatedOutcome, actor: str = "automated_verification") -> WorkflowRecord:
    """Map an automated decision to its initial workflow state.  Never VERIFIED_ACTIVE."""
    state = AUTOMATED_TO_STATE.get(outcome.decision, S.VERIFICATION_ERROR)
    record = WorkflowRecord(state=state, automated=outcome)
    if state == S.ELIGIBLE_PENDING_CONFIRMATION:
        record.required_confirmations = required_checks(outcome)
        reason = ("Automated checks found no contradiction and the essential evidence is present. Documents can be "
                  "consistent and still fabricated, so the campaign awaits independent confirmation; funds are "
                  "blocked until then.")
    elif state == S.NEEDS_MORE_INFORMATION:
        record.information_requests = list(outcome.information_requests) or [
            "Provide the essential document identified by the verifier."]
        reason = "Essential information is missing; a targeted request has been sent. This is not a fraud finding."
    elif state == S.FLAG_FOR_REVIEW:
        reason = "An unresolved material contradiction requires a human reviewer."
    elif state == S.REJECTED:
        reason = "Automated verification found multiple independent high-confidence contradictions."
    else:
        reason = ("Automated verification did not complete; the campaign cannot proceed until it is re-run."
                  if outcome.decision == "VERIFICATION_ERROR" else
                  f"Unrecognised automated decision '{outcome.decision}'; treated as a verification error.")
    if outcome.decision not in AUTOMATED_TO_STATE:
        outcome.errors.append(f"UNKNOWN_DECISION:{outcome.decision}")
    return _move(record, state, "automated_verification", actor, reason)


def effective_source(confirmation: ConfirmationRecord, campaign_text: str = "") -> ContactSource:
    """A contact that appears in the campaign's own text was supplied by the campaign,
    whatever source the verifier selected."""
    if confirmation.contact_reference and campaign_text:
        wanted = re.sub(r"\D", "", confirmation.contact_reference) if "@" not in confirmation.contact_reference \
            else confirmation.contact_reference.casefold()
        for found in _CONTACT.findall(campaign_text):
            candidate = found.casefold() if "@" in found else re.sub(r"\D", "", found)
            if candidate and candidate == wanted:
                return ContactSource.CAMPAIGN_SUPPLIED
    return confirmation.contact_source


def record_confirmation(record: WorkflowRecord, confirmation: ConfirmationRecord,
                        campaign_text: str = "") -> WorkflowRecord:
    """Apply one external confirmation attempt to a pending campaign."""
    if record.state != S.ELIGIBLE_PENDING_CONFIRMATION:
        raise IllegalTransition(f"Confirmations apply only to pending campaigns, not {record.state.value}")
    source = effective_source(confirmation, campaign_text)
    confirmation = confirmation.model_copy(update={"contact_source": source})
    record.confirmations.append(confirmation)
    index = len(record.confirmations) - 1
    requirement = next((r for r in record.required_confirmations if r.check == confirmation.check), None)

    if confirmation.outcome == ConfirmationOutcome.CONTRADICTED:
        return _move(record, S.FLAG_FOR_REVIEW, "confirmation", confirmation.verifier_id,
                     f"{confirmation.check.value} confirmation contradicted a material fact; manual review required.")
    if confirmation.outcome != ConfirmationOutcome.CONFIRMED:
        record.reasons.append(f"{confirmation.check.value}: contact {confirmation.outcome.value.lower()}; "
                              "the check remains open.")
        return record
    if source not in INDEPENDENT_SOURCES:
        record.reasons.append(f"{confirmation.check.value}: confirmed only through contact details supplied by the "
                              "campaign; an independently established contact is still required.")
        return record
    if requirement and not requirement.satisfied:
        requirement.satisfied, requirement.satisfied_by = True, index
    if not record.pending_checks:
        return _move(record, S.VERIFIED_ACTIVE, "confirmation", confirmation.verifier_id,
                     "All required external confirmations were obtained through independent contacts; "
                     "disbursement is now allowed.")
    record.reasons.append(f"{confirmation.check.value} confirmed independently; still pending: "
                          + ", ".join(c.value for c in record.pending_checks) + ".")
    return record


def reviewer_resolution(record: WorkflowRecord, to_state: WorkflowState, reviewer_id: str,
                        reason: str) -> WorkflowRecord:
    """A human reviewer resolves a flagged campaign.  A cleared campaign still has
    to pass external confirmation; reviewers cannot activate directly."""
    if record.state != S.FLAG_FOR_REVIEW:
        raise IllegalTransition("Reviewer resolution applies only to FLAG_FOR_REVIEW")
    if to_state == S.ELIGIBLE_PENDING_CONFIRMATION and not record.required_confirmations:
        record.required_confirmations = required_checks(record.automated)
    if to_state == S.ELIGIBLE_PENDING_CONFIRMATION:
        for requirement in record.required_confirmations:
            requirement.satisfied, requirement.satisfied_by = False, None   # contradiction voids earlier checks
    return _move(record, to_state, "reviewer", reviewer_id, reason)


def reverify(record: WorkflowRecord, outcome: AutomatedOutcome, actor: str = "automated_verification") -> WorkflowRecord:
    """Re-run automated verification after new information or a retried failure."""
    if record.state not in (S.NEEDS_MORE_INFORMATION, S.VERIFICATION_ERROR):
        raise IllegalTransition("Re-verification applies after an information request or a verification error")
    fresh = start(outcome, actor)
    record.automated = outcome
    record.required_confirmations = fresh.required_confirmations
    record.information_requests = fresh.information_requests
    return _move(record, fresh.state, "resubmission", actor, fresh.reasons[-1])


def suspend(record: WorkflowRecord, actor: str, reason: str) -> WorkflowRecord:
    """New adverse evidence about an active campaign: stop disbursement and review."""
    return _move(record, S.FLAG_FOR_REVIEW, "reviewer", actor, reason)


def summarize(records: Iterable[WorkflowRecord]) -> dict:
    counts = {state.value: 0 for state in WorkflowState}
    confirmations = 0
    for record in records:
        counts[record.state.value] += 1
        confirmations += len(record.pending_checks)
    return {"states": counts, "external_confirmations_required": confirmations}
