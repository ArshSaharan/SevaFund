"""External confirmation is mandatory (hybrid v3, development only).

Automated verification can at most make a campaign ELIGIBLE_PENDING_CONFIRMATION.  Consistent documents are not
proof of authenticity: a fabricated institution can produce a perfectly consistent dossier.  Activation (and any
disbursement) needs the beneficiary, the institution and the payment destination each confirmed through an
independently sourced contact (registry, official directory, platform KYC or a prior verified record), recorded in
the frozen approval workflow.  This module only adds an explicit, testable guard on top of that workflow; it does
not change it.
"""
from typing import Iterable

from app.services.development_approval_workflow import AutomatedOutcome, start
from app.services.development_approval_workflow.schemas import (ConfirmationCheck, ConfirmationOutcome,
                                                                INDEPENDENT_SOURCES, WorkflowRecord, WorkflowState)

REQUIRED_CHECKS = {ConfirmationCheck.BENEFICIARY, ConfirmationCheck.PAYMENT_DESTINATION, ConfirmationCheck.INSTITUTION}


def start_record(decision: str, category: str, beneficiary_type, information_requests: Iterable[str] = ()) -> WorkflowRecord:
    """Initial workflow record; the institution check is always required (names_institution=True)."""
    return start(AutomatedOutcome(decision=decision, category=category, beneficiary_type=beneficiary_type,
                                  names_institution=True, information_requests=list(information_requests)))


def activation_status(record: WorkflowRecord) -> dict:
    required = {r.check for r in record.required_confirmations}
    independent = all(
        r.satisfied_by is not None
        and record.confirmations[r.satisfied_by].outcome == ConfirmationOutcome.CONFIRMED
        and record.confirmations[r.satisfied_by].contact_source in INDEPENDENT_SOURCES
        for r in record.required_confirmations if r.satisfied)
    complete = REQUIRED_CHECKS <= required and not record.pending_checks and independent
    allowed = record.state == WorkflowState.VERIFIED_ACTIVE and complete
    return {"state": record.state.value, "activation_allowed": allowed,
            "disbursement_allowed": record.disbursement_allowed and allowed,
            "pending_checks": [c.value for c in record.pending_checks],
            "required_checks": sorted(c.value for c in required),
            "authenticity": "CONFIRMED_BY_INDEPENDENT_SOURCES" if allowed else "UNCONFIRMED"}
