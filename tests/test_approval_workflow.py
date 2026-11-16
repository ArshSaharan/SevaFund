"""Tests for the development-only ELIGIBLE_PENDING_EXTERNAL_VERIFICATION workflow."""
import itertools
import json
from pathlib import Path

import pytest

from app.services.development_approval_workflow import (
    AutomatedOutcome, ConfirmationCheck, ConfirmationOutcome, ConfirmationRecord, ContactSource, IllegalTransition,
    WorkflowState, record_confirmation, reverify, reviewer_resolution, start, suspend,
)

ROOT = Path(__file__).resolve().parents[1]
S = WorkflowState
C = ConfirmationCheck
INDEPENDENT = [ContactSource.OFFICIAL_REGISTRY, ContactSource.OFFICIAL_DIRECTORY, ContactSource.PLATFORM_KYC,
               ContactSource.PRIOR_VERIFIED_RECORD]


def outcome(decision="APPROVED", category="MEDICAL", beneficiary_type="SELF", **extra):
    return AutomatedOutcome(decision=decision, category=category, beneficiary_type=beneficiary_type, **extra)


def confirm(check, result=ConfirmationOutcome.CONFIRMED, source=ContactSource.OFFICIAL_DIRECTORY, contact=""):
    return ConfirmationRecord(check=check, outcome=result, contact_source=source, contact_reference=contact,
                              verifier_id="verifier-7")


def confirm_all(record, source=ContactSource.OFFICIAL_DIRECTORY):
    for check in list(record.pending_checks):
        record = record_confirmation(record, confirm(check, source=source))
    return record


# ------------------------------------------------------------- automated mapping
@pytest.mark.parametrize("decision,state", [
    ("APPROVED", S.ELIGIBLE_PENDING_CONFIRMATION), ("NEEDS_MORE_INFORMATION", S.NEEDS_MORE_INFORMATION),
    ("FLAG_FOR_REVIEW", S.FLAG_FOR_REVIEW), ("REJECTED", S.REJECTED), ("VERIFICATION_ERROR", S.VERIFICATION_ERROR),
    ("AUTO_APPROVE", S.VERIFICATION_ERROR), ("", S.VERIFICATION_ERROR),
])
def test_automated_decisions_map_to_states_and_never_activate(decision, state):
    record = start(outcome(decision))
    assert record.state == state
    assert record.state != S.VERIFIED_ACTIVE and not record.disbursement_allowed
    assert record.history[0].from_state is None and record.history[0].trigger == "automated_verification"


def test_pending_confirmation_is_not_a_fraud_detection():
    assert not start(outcome("APPROVED")).is_fraud_detection
    assert not start(outcome("NEEDS_MORE_INFORMATION")).is_fraud_detection
    assert not start(outcome("VERIFICATION_ERROR")).is_fraud_detection
    assert start(outcome("FLAG_FOR_REVIEW")).is_fraud_detection and start(outcome("REJECTED")).is_fraud_detection


@pytest.mark.parametrize("category,beneficiary_type,expected", [
    ("MEDICAL", "SELF", {C.BENEFICIARY, C.PAYMENT_DESTINATION, C.INSTITUTION}),
    ("EDUCATION", "SELF", {C.BENEFICIARY, C.PAYMENT_DESTINATION, C.INSTITUTION}),
    ("COMMUNITY", "ORGANISATION", {C.BENEFICIARY, C.PAYMENT_DESTINATION, C.INSTITUTION}),
])
def test_pending_campaigns_require_beneficiary_payee_and_institution(category, beneficiary_type, expected):
    record = start(outcome("APPROVED", category, beneficiary_type))
    assert set(record.pending_checks) == expected
    institution = next(r for r in record.required_confirmations if r.check == C.INSTITUTION).description
    assert {"MEDICAL": "hospital", "EDUCATION": "institution", "COMMUNITY": "registration"}[category] in institution.lower()


def test_information_request_is_targeted():
    record = start(outcome("NEEDS_MORE_INFORMATION", information_requests=["Upload the hospital's dated estimate."]))
    assert record.information_requests == ["Upload the hospital's dated estimate."]
    assert "not a fraud finding" in record.reasons[-1]


# ---------------------------------------------------------- external confirmation
@pytest.mark.parametrize("source", INDEPENDENT)
def test_all_independent_confirmations_activate_and_release_funds(source):
    record = confirm_all(start(outcome()), source)
    assert record.state == S.VERIFIED_ACTIVE and record.disbursement_allowed
    assert all(r.satisfied for r in record.required_confirmations)


def test_partial_confirmation_keeps_funds_blocked():
    record = start(outcome())
    record = record_confirmation(record, confirm(C.BENEFICIARY))
    record = record_confirmation(record, confirm(C.INSTITUTION))
    assert record.state == S.ELIGIBLE_PENDING_CONFIRMATION and not record.disbursement_allowed
    assert record.pending_checks == [C.PAYMENT_DESTINATION]


def test_campaign_supplied_contact_never_satisfies_a_check():
    record = confirm_all(start(outcome()), ContactSource.CAMPAIGN_SUPPLIED)
    assert record.state == S.ELIGIBLE_PENDING_CONFIRMATION and not record.disbursement_allowed
    assert any("supplied by the campaign" in reason for reason in record.reasons)


@pytest.mark.parametrize("contact", ["+91 98450 12345", "billing@sunrise-hospital.example"])
def test_contact_found_in_campaign_uploads_is_treated_as_campaign_supplied(contact):
    uploads = f"Estimate No. 44 ... For queries call +91-98450-12345 or write to billing@sunrise-hospital.example"
    record = start(outcome())
    record = record_confirmation(record, confirm(C.INSTITUTION, source=ContactSource.OFFICIAL_DIRECTORY,
                                                 contact=contact), campaign_text=uploads)
    assert record.confirmations[-1].contact_source == ContactSource.CAMPAIGN_SUPPLIED
    assert C.INSTITUTION in record.pending_checks


def test_independent_contact_not_in_uploads_counts():
    record = record_confirmation(start(outcome()), confirm(C.INSTITUTION, contact="+91 80 2222 0000"),
                                 campaign_text="Call +91-98450-12345")
    assert C.INSTITUTION not in record.pending_checks


def test_contradicting_confirmation_routes_to_review_and_blocks_funds():
    record = record_confirmation(start(outcome()), confirm(C.INSTITUTION, ConfirmationOutcome.CONTRADICTED))
    assert record.state == S.FLAG_FOR_REVIEW and not record.disbursement_allowed and record.is_fraud_detection


@pytest.mark.parametrize("result", [ConfirmationOutcome.UNREACHABLE, ConfirmationOutcome.INCONCLUSIVE])
def test_unreachable_or_inconclusive_contact_leaves_check_open(result):
    record = record_confirmation(start(outcome()), confirm(C.PAYMENT_DESTINATION, result))
    assert record.state == S.ELIGIBLE_PENDING_CONFIRMATION and C.PAYMENT_DESTINATION in record.pending_checks


def test_confirmations_only_apply_to_pending_campaigns():
    for decision in ("NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR"):
        with pytest.raises(IllegalTransition):
            record_confirmation(start(outcome(decision)), confirm(C.BENEFICIARY))


def test_no_sequence_of_incomplete_or_dependent_confirmations_releases_funds():
    """Exhaustive over every ordered sequence of up to three attempts drawn from
    {each check} x {each outcome} x {independent, campaign-supplied}."""
    attempts = [(check, result, source) for check in C for result in ConfirmationOutcome
                for source in (ContactSource.OFFICIAL_REGISTRY, ContactSource.CAMPAIGN_SUPPLIED)]
    for sequence in itertools.product(attempts, repeat=3):
        record = start(outcome())
        for check, result, source in sequence:
            if record.state != S.ELIGIBLE_PENDING_CONFIRMATION:
                break
            record = record_confirmation(record, confirm(check, result, source))
        independently_confirmed = {c.check for c in record.confirmations
                                   if c.outcome == ConfirmationOutcome.CONFIRMED
                                   and c.contact_source != ContactSource.CAMPAIGN_SUPPLIED}
        contradicted = any(c.outcome == ConfirmationOutcome.CONTRADICTED for c in record.confirmations)
        if record.disbursement_allowed:
            assert independently_confirmed == set(C) and not contradicted


# ------------------------------------------------------------ reviewers & errors
def test_reviewer_cannot_activate_directly_and_cleared_campaign_needs_fresh_confirmation():
    record = record_confirmation(start(outcome()), confirm(C.BENEFICIARY))
    record = record_confirmation(record, confirm(C.INSTITUTION, ConfirmationOutcome.CONTRADICTED))
    with pytest.raises(IllegalTransition):
        reviewer_resolution(record, S.VERIFIED_ACTIVE, "reviewer-2", "looks fine")
    record = reviewer_resolution(record, S.ELIGIBLE_PENDING_CONFIRMATION, "reviewer-2", "explained by hospital")
    assert set(record.pending_checks) == set(C)   # earlier confirmations are voided after a contradiction


def test_reviewer_can_reject_and_rejection_is_terminal():
    record = reviewer_resolution(start(outcome("FLAG_FOR_REVIEW")), S.REJECTED, "reviewer-2", "forged estimate")
    assert record.state == S.REJECTED
    with pytest.raises(IllegalTransition):
        reverify(record, outcome("APPROVED"))


def test_verification_error_can_only_be_retried_never_approved():
    record = start(outcome("VERIFICATION_ERROR", errors=["extraction failed (KeyError)"]))
    with pytest.raises(IllegalTransition):
        record_confirmation(record, confirm(C.BENEFICIARY))
    retried = reverify(record, outcome("APPROVED"))
    assert retried.state == S.ELIGIBLE_PENDING_CONFIRMATION and not retried.disbursement_allowed


def test_information_response_is_reverified():
    record = reverify(start(outcome("NEEDS_MORE_INFORMATION")), outcome("FLAG_FOR_REVIEW"))
    assert record.state == S.FLAG_FOR_REVIEW
    assert [t.to_state for t in record.history] == [S.NEEDS_MORE_INFORMATION, S.FLAG_FOR_REVIEW]


def test_active_campaign_can_be_suspended():
    record = suspend(confirm_all(start(outcome())), "trust-team", "Hospital later reported the estimate as altered")
    assert record.state == S.FLAG_FOR_REVIEW and not record.disbursement_allowed


def test_every_transition_is_recorded_with_actor_and_reason():
    record = confirm_all(start(outcome()))
    assert [t.to_state for t in record.history] == [S.ELIGIBLE_PENDING_CONFIRMATION, S.VERIFIED_ACTIVE]
    assert all(t.actor and t.reason for t in record.history)


# -------------------------------------------------- end to end with frozen V3
def _v3_case(case_id):
    from evaluation.evaluate_development_verifier_v3 import v3_input
    rows = [json.loads(line) for line in (ROOT / "evaluation/development_scenarios_v3.jsonl").read_text().splitlines()]
    return v3_input(next(r for r in rows if r["case_id"] == case_id)["input"])


def test_frozen_v3_approval_becomes_pending_not_active():
    from app.services.development_verifier_v3 import verify_case
    case = _v3_case("V3D-001")
    result = verify_case(case)
    record = start(AutomatedOutcome.from_v3(result, case))
    if result.decision.value == "APPROVED":
        assert record.state == S.ELIGIBLE_PENDING_CONFIRMATION
    assert not record.disbursement_allowed


def test_v3_stage_failure_becomes_verification_error_state():
    from app.services.development_verifier_v3 import verify_case

    def failing_reasoner(ctx):
        raise TimeoutError("simulated external check timeout")

    case = _v3_case("V3D-001")
    record = start(AutomatedOutcome.from_v3(verify_case(case, reasoners=[failing_reasoner]), case))
    assert record.state in (S.VERIFICATION_ERROR, S.FLAG_FOR_REVIEW) and not record.disbursement_allowed


def test_keyword_free_checker_detects_known_lexicon_words():
    import sys
    sys.path.insert(0, str(ROOT / "evaluation"))
    from check_keyword_free_fraud import keyword_hits, lexicons
    patterns = lexicons()
    assert keyword_hits("Kindly transfer straight to my cousin's GPay number", patterns)
    assert keyword_hits("The fee was already paid in full by the bursary.", patterns)
    assert not keyword_hits("The ward bill lists two nights and one dressing change.", patterns)
