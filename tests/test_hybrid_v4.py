"""Hybrid v4 (development only): offline tests.  No network, no API call."""
import ast
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from app.services.development_approval_workflow.schemas import ConfirmationOutcome as O, ContactSource as Src  # noqa: E402
from app.services.development_hybrid_v3 import combine as hybrid_v3_combine, v3_case  # noqa: E402
from app.services.development_hybrid_v4 import (ASSISTED_COST_CONFIRMATION, Check, Confirmation,  # noqa: E402
                                                IllegalTransition, activation_status, assess_case, assisted_cost_review,
                                                check_payment_accounts, record_confirmation, reviewer_resolution, start)
from app.services.development_approval_workflow.schemas import WorkflowState  # noqa: E402
from app.services.development_verifier_v3 import verify_case  # noqa: E402
from app.services.development_verifier_v3.config import DEFAULT_CONFIG  # noqa: E402

REF = date(2026, 11, 14)
APPROVE = {"status": "OK", "decision": "APPROVED", "concerns": [], "missing_requirements": []}
FAILED = {"status": "FAILED", "failure_category": "SERVER_ERROR"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")
    import app.services.gemini_api as gemini_api
    import app.services.rag as rag
    monkeypatch.setattr(gemini_api, "post_json", forbidden)
    monkeypatch.setattr(rag, "post_json", forbidden)


def chunks_of(case):
    return [{"title": d["title"], "text": d["content"]} for d in case["documents"]]


def medical(goal=185000, estimate="Total estimate Rs 1,85,000.", extra_docs=(), note_text=None, bill_date="11/11/2026"):
    docs = [{"title": "Hospital estimate", "doc_type": "HOSPITAL_ESTIMATE",
             "content": f"Sushruta Hospital, Wardha Road, Nagpur 440015. Estimate No. SH/EST/26/4471 Date: {bill_date}\n"
                        "Patient: Kamala Bai, 68 F, UHID SH-208813\nProcedure: Left hip hemiarthroplasty\nImplant Rs 75,000; "
                        "Surgery and OT Rs 55,000; Ward 4 days Rs 32,000; Medicines Rs 23,000\n"
                        f"{estimate} Planned surgery date: 21/11/2026. Billing Executive (signed)"},
            {"title": "Orthopaedic note", "doc_type": "CLINICAL_NOTE",
             "content": note_text or "Sushruta Hospital casualty 10/11/2026. Kamala Bai 68 F. Displaced fracture neck of "
                                     "left femur after a fall at home. Advised hemiarthroplasty. Dr P. Wankhede MS Ortho"}]
    return {"title": "Hip surgery for Kamala Bai", "category": "MEDICAL", "goal_amount": goal, "goal_currency": "INR",
            "story": "Kamala Bai, 68, fractured her left hip. Sushruta Hospital will operate next week.",
            "beneficiary_name": "Kamala Bai", "beneficiary_type": "SELF", "city": "Nagpur", "state": "Maharashtra",
            "submitted_on": REF.isoformat(), "documents": docs + list(extra_docs)}


def decide(case, gemini=APPROVE):
    return assess_case(case, gemini, chunks_of(case), REF)


def confirm(record, check, outcome=O.CONFIRMED, source=Src.PLATFORM_KYC, stated=None, other=0, reference="", text=""):
    return record_confirmation(record, Confirmation(check=check, outcome=outcome, contact_source=source,
                                                    contact_reference=reference, verifier_id="verifier-1",
                                                    stated_amount_inr=stated, other_payers_inr=other), text)


def pending_record(goal=185000):
    case = medical(goal=goal)
    return start("APPROVED", case), case


def confirm_identity_checks(record):
    for check in (Check.BENEFICIARY, Check.INSTITUTION, Check.PAYMENT_DESTINATION):
        confirm(record, check, source=Src.OFFICIAL_DIRECTORY)


# ------------------------------------------------------------------ activation needs four independent checks
def test_three_checks_are_not_enough_amount_is_required():
    record, _ = pending_record()
    confirm_identity_checks(record)
    assert record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION and record.pending_checks == [Check.AMOUNT]
    confirm(record, Check.AMOUNT, source=Src.OFFICIAL_DIRECTORY, stated=185000)
    status = activation_status(record)
    assert status["activated"] and status["activation_valid"] and status["disbursement_allowed"]
    assert status["independently_confirmed"] == ["AMOUNT", "BENEFICIARY", "INSTITUTION", "PAYMENT_DESTINATION"]
    assert record.disbursement_limit_inr == 185000


@pytest.mark.parametrize("stated, other, goal, active", [(185000, 0, 185000, True), (180000, 0, 189000, True),
                                                         (180000, 0, 189100, False), (160000, 100000, 60000, True),
                                                         (160000, 100000, 160000, False), (90000, 90000, 90000, False)])
def test_amount_tolerance_and_other_payers(stated, other, goal, active):
    record, _ = pending_record(goal)
    confirm_identity_checks(record)
    confirm(record, Check.AMOUNT, source=Src.OFFICIAL_DIRECTORY, stated=stated, other=other)
    assert (record.state == WorkflowState.VERIFIED_ACTIVE) is active
    if not active:
        assert record.state == WorkflowState.FLAG_FOR_REVIEW
        assert "exceeds the independently confirmed need" in record.audit.entries[-1].data["reason"]


def test_disbursement_is_limited_to_the_confirmed_need():
    record, _ = pending_record(goal=189000)
    confirm_identity_checks(record)
    confirm(record, Check.AMOUNT, source=Src.OFFICIAL_DIRECTORY, stated=180000)
    assert record.state == WorkflowState.VERIFIED_ACTIVE and record.disbursement_limit_inr == 180000


def test_issuer_without_a_figure_or_unreachable_leaves_the_check_open():
    record, _ = pending_record()
    confirm_identity_checks(record)
    confirm(record, Check.AMOUNT, source=Src.OFFICIAL_DIRECTORY, stated=None)
    confirm(record, Check.AMOUNT, outcome=O.UNREACHABLE, source=Src.OFFICIAL_DIRECTORY)
    assert record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION and record.pending_checks == [Check.AMOUNT]


@pytest.mark.parametrize("check", list(Check))
def test_any_independent_contradiction_sends_the_campaign_to_review(check):
    record, _ = pending_record()
    confirm(record, check, outcome=O.CONTRADICTED, source=Src.OFFICIAL_DIRECTORY, stated=185000)
    assert record.state == WorkflowState.FLAG_FOR_REVIEW and not activation_status(record)["activated"]


def test_campaign_supplied_contacts_never_satisfy_a_check():
    record, case = pending_record()
    for check in Check:
        confirm(record, check, source=Src.CAMPAIGN_SUPPLIED, stated=185000)
    assert record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION and len(record.pending_checks) == 4
    text = "Call the hospital helpdesk on 98110 44321 to confirm."
    confirm(record, Check.INSTITUTION, source=Src.OFFICIAL_DIRECTORY, reference="98110 44321", text=text)
    assert record.confirmations[-1].contact_source == Src.CAMPAIGN_SUPPLIED and Check.INSTITUTION in record.pending_checks


def test_automation_and_reviewers_cannot_activate():
    record, _ = pending_record()
    assert record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION
    confirm(record, Check.INSTITUTION, outcome=O.CONTRADICTED, source=Src.OFFICIAL_DIRECTORY)
    with pytest.raises(IllegalTransition):
        reviewer_resolution(record, WorkflowState.VERIFIED_ACTIVE, "reviewer-1", "looks fine")
    reviewer_resolution(record, WorkflowState.ELIGIBLE_PENDING_CONFIRMATION, "reviewer-1", "explained")
    assert len(record.pending_checks) == 4                    # clearing voids earlier confirmations
    for decision in ("NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "VERIFICATION_ERROR", "REJECTED"):
        other = start(decision, medical())
        with pytest.raises(IllegalTransition):
            confirm(other, Check.BENEFICIARY)


# ------------------------------------------------------------------ assisted route for missing quotations
def informal_case():
    return {"title": "Spine surgery at the government hospital for Bhola", "category": "MEDICAL", "goal_amount": 120000,
            "story": "Bhola Prasad injured his spine. The government hospital operates free but he must buy implants.",
            "beneficiary_name": "Bhola Prasad", "beneficiary_type": "SELF", "city": "Patna", "state": "Bihar",
            "submitted_on": REF.isoformat(),
            "documents": [{"title": "List of items to purchase", "doc_type": "HOSPITAL_LETTER",
                           "content": "Government Medical College Hospital, Patna. Patient Bhola Prasad 39 M. Items to be "
                                      "purchased before surgery: pedicle screws 6, rods 2. Date 08/11/2026. Unit In-charge"},
                          {"title": "Admission slip", "doc_type": "CLINICAL_NOTE",
                           "content": "GMCH Patna. Admitted 07/11/2026. Bhola Prasad 39 M. L1 burst fracture. Planned "
                                      "posterior fixation. Dr A. K. Singh"}]}


def test_missing_quotation_gets_an_information_request_and_the_assisted_route():
    result = decide(informal_case(), {"status": "OK", "decision": "NEEDS_MORE_INFORMATION", "concerns": [],
                                      "missing_requirements": ["A cost estimate for the implants is required."]})
    assert result.decision == "NEEDS_MORE_INFORMATION" and result.manual_route == ASSISTED_COST_CONFIRMATION
    assert any("caseworker can also obtain the amount" in r for r in result.information_requests)
    assert result.review_basis is None                          # an information request is not a fraud finding


def test_assisted_route_still_needs_all_four_independent_checks():
    case = informal_case()
    result = decide(case)
    record = start(result.decision, case, result.information_requests, result.manual_route)
    assisted_cost_review(record, "caseworker-1", "No formal quotation; obtain the amount from the hospital.")
    assert record.state == WorkflowState.ELIGIBLE_PENDING_CONFIRMATION and len(record.pending_checks) == 4
    confirm_identity_checks(record)
    confirm(record, Check.AMOUNT, source=Src.OFFICIAL_DIRECTORY, stated=100000)       # issuer states less than the goal
    assert record.state == WorkflowState.FLAG_FOR_REVIEW


def test_assisted_route_is_not_offered_when_identity_or_need_is_missing():
    case = informal_case()
    gemini = {"status": "OK", "decision": "NEEDS_MORE_INFORMATION", "concerns": [],
              "missing_requirements": ["Provide the beneficiary's identity proof."]}
    result = decide(case, gemini)
    assert result.decision == "NEEDS_MORE_INFORMATION" and result.manual_route is None
    record = start(result.decision, case, result.information_requests, result.manual_route)
    with pytest.raises(IllegalTransition):
        assisted_cost_review(record, "caseworker-1", "attempt")


# ------------------------------------------------------------------ Gemini cannot reject; warnings must be grounded
def test_an_unquoted_gemini_rejection_is_only_an_unverified_review_referral():
    gemini = {"status": "OK", "decision": "REJECTED", "missing_requirements": [],
              "concerns": [{"category": "SUSPECTED_FRAUD", "description": "Likely a scam."}]}
    result = decide(medical(), gemini)
    assert result.decision == "FLAG_FOR_REVIEW" and result.review_basis == "UNVERIFIED_MODEL_SUSPICION"
    assert {f.source for f in result.findings} == {"GEMINI_UNVERIFIED"}
    assert "not a fraud determination" in result.explanation


def test_a_quoted_gemini_contradiction_carries_its_document_evidence():
    case = medical(note_text="Sushruta Hospital casualty 10/11/2026. Kamala Bai 68 F. Hairline crack, no surgery is "
                             "indicated. Dr P. Wankhede")
    quote = "Hairline crack, no surgery is indicated"
    gemini = {"status": "OK", "decision": "FLAG_FOR_REVIEW", "missing_requirements": [],
              "concerns": [{"category": "CONTRADICTION", "description": "The note says surgery is not needed.",
                            "document_title": "Orthopaedic note", "evidence_quote": quote}]}
    result = decide(case, gemini)
    assert result.decision == "FLAG_FOR_REVIEW"
    assert any(e.get("quote") == quote for f in result.findings for e in f.evidence)


def test_gemini_never_produces_rejected_on_the_engineering_fixtures():
    from independent_v5 import config, retrieval
    rejection = {"status": "OK", "decision": "REJECTED", "missing_requirements": [],
                 "concerns": [{"category": "SUSPECTED_FRAUD", "description": "Scam."}]}
    for row in config.read_jsonl(config.FIXTURES / "submission.jsonl"):
        data = row["input"]
        chunks, _ = asyncio.run(retrieval.retrieve(data))
        result = assess_case(data, rejection, chunks, date.fromisoformat(data["submitted_on"]))
        assert result.decision != "REJECTED" or result.v3_decision == "REJECTED"


# ------------------------------------------------------------------ payment-account conflicts
def bank_doc(title, holder, account):
    return {"title": title, "doc_type": "LETTER", "content": f"Please pay to Account name: {holder} A/c No. {account}, HDFC Bank."}


def test_payment_account_conflict_same_holder_different_accounts():
    case = medical(extra_docs=[bank_doc("Hospital bank letter", "Sushruta Hospital", "30418877201"),
                               bank_doc("Donor letter", "Sushruta Hospital", "50100234998812")])
    findings = check_payment_accounts(case)
    assert len(findings) == 1 and "30418877201" in findings[0].summary
    result = decide(case)
    assert result.decision == "FLAG_FOR_REVIEW" and result.triggers[0] == "PAYMENT_ACCOUNT_CONFLICT"
    assert result.review_basis == "DETERMINISTIC_FINDING" and len(result.findings[-1].evidence) == 2


def test_payment_account_conflict_is_found_even_when_gemini_fails():
    case = medical(extra_docs=[bank_doc("Hospital bank letter", "Sushruta Hospital", "30418877201"),
                               bank_doc("Donor letter", "Sushruta Hospital", "50100234998812")])
    assert decide(case, FAILED).decision == "FLAG_FOR_REVIEW"
    assert decide(medical(), FAILED).decision == "VERIFICATION_ERROR"


@pytest.mark.parametrize("docs", [
    [("A", "Sushruta Hospital", "30418877201"), ("B", "Sushruta Hospital", "30418877201")],      # same account repeated
    [("A", "Sushruta Hospital", "30418877201"), ("B", "Kamala Bai", "11223344556")],              # different holders
    [("A", "Sushruta Hospital", "1234567")],                                                       # too short to compare
])
def test_payment_accounts_without_a_conflict(docs):
    assert check_payment_accounts({"documents": [bank_doc(t, h, a) for t, h, a in docs]}) == []


# ------------------------------------------------------------------ date interpretation preserved
def test_scheduled_future_surgery_is_not_a_future_dated_document():
    assert decide(medical()).decision == "APPROVED"


def test_a_bill_issued_after_submission_is_reviewed():
    result = decide(medical(bill_date="20/11/2026"))
    assert result.decision == "FLAG_FOR_REVIEW" and result.findings


def test_an_expired_estimate_is_an_information_request():
    result = decide(medical(bill_date="02/09/2025"))
    assert result.decision == "NEEDS_MORE_INFORMATION"


# ------------------------------------------------------------------ explanations and audit record
def test_every_decision_has_an_explanation_and_detections_have_findings():
    for case, gemini in [(medical(), APPROVE), (medical(goal=450000), APPROVE), (informal_case(), APPROVE),
                         (medical(), FAILED)]:
        result = decide(case, gemini)
        assert result.explanation.startswith(f"Decision: {result.decision}.") and result.reasons
        assert result.case_fingerprint and result.policy_version == "hybrid-v4-dev-1"
        if result.decision in ("FLAG_FOR_REVIEW", "REJECTED"):
            assert result.findings and result.review_basis


def test_audit_log_is_hash_chained_and_detects_tampering():
    record, _ = pending_record()
    confirm_identity_checks(record)
    confirm(record, Check.AMOUNT, source=Src.OFFICIAL_DIRECTORY, stated=185000)
    assert record.audit.verify() and [e.event for e in record.audit.entries][:2] == ["AUTOMATED_DECISION", "STATE_CHANGE"]
    record.audit.entries[2].data["outcome"] = "CONTRADICTED"
    assert not record.audit.verify() and not activation_status(record)["activation_valid"]


def test_hybrid_v4_matches_hybrid_v3_except_for_its_documented_additions():
    """Regression: on the engineering fixtures hybrid v4 makes hybrid v3's decision unless a payment-account conflict
    applies; the assisted route only annotates information requests."""
    from independent_v5 import config, retrieval
    for gemini in (APPROVE, {"status": "OK", "decision": "NEEDS_MORE_INFORMATION", "concerns": [],
                             "missing_requirements": ["A cost document is needed."]}):
        for row in config.read_jsonl(config.FIXTURES / "submission.jsonl"):
            data = row["input"]
            reference = date.fromisoformat(data["submitted_on"])
            chunks, _ = asyncio.run(retrieval.retrieve(data))
            v3 = verify_case(v3_case(data), DEFAULT_CONFIG)
            hv3 = hybrid_v3_combine(data, v3, gemini, chunks, reference)
            v4 = assess_case(data, gemini, chunks, reference)
            if not check_payment_accounts(data):
                assert v4.decision == hv3.decision, row["case_id"]


# ------------------------------------------------------------------ isolation and the final evaluation
def test_production_does_not_import_hybrid_v4_and_frozen_packages_are_untouched():
    """Only the development integration (loaded lazily, and only when SEVAFUND_DEV_HYBRID_V4 is on) imports hybrid v4."""
    allowed = {ROOT / "app/services/dev_hybrid_v4_integration.py"}
    for path in (ROOT / "app").rglob("*.py"):
        if "development_hybrid_v4" in path.parts or path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
                  {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any("development_hybrid_v4" in m for m in modules), path
    assert 'os.getenv("GEMINI_MODEL", "gemini-3.8-flash")' in (ROOT / "app/config.py").read_text()


def test_final_evaluation_reproduces_its_committed_metrics(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "evaluation" / "final_evaluation"))
    import run_final_evaluation as fe
    committed = json.loads((fe.RESULTS / "metrics.json").read_text())
    monkeypatch.setattr(fe, "RESULTS", tmp_path)
    fresh = fe.main()
    assert json.loads(json.dumps(fresh["metrics"], sort_keys=True)) == committed["metrics"]
    assert fresh["meta"]["network_connections_attempted"] == 0 and fresh["meta"]["api_calls"] == 0
