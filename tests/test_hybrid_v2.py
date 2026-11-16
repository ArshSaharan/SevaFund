"""Tests for the development-only improved V3 + Gemini path (hybrid v2).

Warning texts here are newly written, not copied from the 10-case evaluation outputs, so they test whether the
classifier generalises beyond the cases that motivated it."""
import asyncio
import hashlib
import itertools
import json
from datetime import date
from pathlib import Path

import pytest

from app.services.development_gemini_verification import (
    assess_dates, build_concerns, classify_text, combine, verify_with_gemini,
)
from app.services.development_gemini_verification.prompt import build_prompt
from app.services.gemini_api import GeminiAPIError

ROOT = Path(__file__).resolve().parents[1]
REF = date(2026, 10, 30)
EVIDENCE = [{"title": "Fee ledger", "text": "Ledger 2026/77: semester fee of ₹48,500 paid in full on 02 August 2026 by the "
                                            "district bursary. Outstanding balance: nil."}]
STORY = "Help Meera pay her semester fee of ₹48,500 before the deadline."


# ------------------------------------------------------------------ dates
@pytest.mark.parametrize("text,status", [
    ("Estimate dated 12 October 2026", "VALID"),
    ("Estimate dated 31 October 2026", "VALID"),                 # within the 1-day grace period
    ("Estimate dated 14 January 2027", "FUTURE"),
    ("Quotation valid until 01/09/2026", "EXPIRED"),
    ("Quotation valid until 01/12/2026", "VALID"),
    ("Report dated 03 March 2025", "EXPIRED"),                   # older than the 365-day maximum age
    ("Surgery scheduled for 05 January 2027", "MENTIONED"),      # a future event, legitimately
    ("Fee payable by 15/12/2026", "MENTIONED"),
])
def test_document_dates_are_classified_against_the_reference_date(text, status):
    assessment = assess_dates([("Doc", text)], REF)
    assert [d.status for d in assessment.dates] == [status]


def test_spurious_future_date_claim_is_vetoed_and_genuine_one_is_kept():
    current = assess_dates([("Bill", "Bill dated 04 September 2026")], REF)
    concern = build_concerns({"red_flags": ["The bill carries a future date (04 September 2026)."]}, [], "", current)[0]
    assert concern.type == "DATE_CLAIM" and concern.vetoed
    future = assess_dates([("Bill", "Bill dated 04 September 2027")], REF)
    assert not build_concerns({"red_flags": ["The bill is future-dated."]}, [], "", future)[0].vetoed


# ------------------------------------------------------------- concerns
@pytest.mark.parametrize("text,kind", [
    ("Stamp on the discharge note appears to have been altered after issue", "FRAUD_INDICATOR"),
    ("The hospital ledger shows this bill was already settled by the insurer", "FRAUD_INDICATOR"),
    ("Admission card belongs to a different patient than the beneficiary", "FRAUD_INDICATOR"),
    ("Requested sum of ₹90,000 conflicts with the ₹60,000 shown on the quotation", "CONTRADICTION"),
    ("Discrepancy in enrolment year between the bonafide letter and the story", "CONTRADICTION"),
    ("No discharge summary or doctor's prescription was uploaded", "INFORMATION_GAP"),
    ("Registration with the society registrar is not yet confirmed", "INFORMATION_GAP"),
    ("Narrative is vague about the treatment timeline", "INFORMATION_GAP"),
    ("The fee notice is outdated", "DATE_CLAIM"),
    ("Beneficiary is a minor represented by a guardian", "OTHER"),
])
def test_warnings_are_separated_into_fraud_signals_and_information_gaps(text, kind):
    assert classify_text(text) == kind


def test_text_concern_is_grounded_only_by_document_specific_facts():
    grounded = build_concerns({"red_flags": ["Story says the fee is unpaid, but the ledger shows a nil balance."]},
                              EVIDENCE, STORY, None)[0]
    from_story_only = build_concerns({"red_flags": ["The ₹48,500 fee request is inconsistent with typical costs."]},
                                     EVIDENCE, STORY, None)[0]
    assert grounded.type in ("CONTRADICTION", "FRAUD_INDICATOR") and grounded.grounded
    assert from_story_only.type == "CONTRADICTION" and not from_story_only.grounded


def test_structured_concern_needs_a_quote_found_in_the_evidence():
    real = {"concerns": [{"category": "SUSPECTED_FRAUD", "description": "Fee already paid",
                          "evidence_quote": "paid in full on 02 August 2026 by the district bursary"}]}
    invented = {"concerns": [{"category": "SUSPECTED_FRAUD", "description": "Fee already paid",
                              "evidence_quote": "refund issued to the student's father in July"}]}
    assert build_concerns(real, EVIDENCE, STORY, None)[0].grounded
    assert not build_concerns(invented, EVIDENCE, STORY, None)[0].grounded


# ----------------------------------------------------------------- policy
def gem(decision="APPROVED", flags=(), missing=(), status="OK", concerns=None):
    return {"status": status, "decision": decision, "red_flag_texts": list(flags), "missing_requirements": list(missing),
            "concerns": concerns or [], "failure_category": None if status == "OK" else "READ_TIMEOUT"}


def decide(v3="APPROVED", gemini=None, docs=None, evidence=EVIDENCE, story=STORY):
    dates = assess_dates(docs or [("Fee ledger", EVIDENCE[0]["text"])], REF)
    return combine(v3, gemini, evidence, story, dates, category="EDUCATION")


def test_generic_warning_on_an_information_request_does_not_escalate():
    out = decide(gemini=gem("NEEDS_MORE_INFORMATION", ["Fee notice lacks a registrar seal", "Student ID not uploaded"],
                            ["Stamped fee notice"]))
    assert out.decision == "NEEDS_MORE_INFORMATION" and out.triggers == ["GEMINI_INFORMATION_REQUEST"]
    assert "Stamped fee notice" in out.information_requests


def test_grounded_contradiction_escalates_even_without_a_gemini_flag():
    out = decide(gemini=gem("NEEDS_MORE_INFORMATION", ["Story says the fee is unpaid, but the ledger shows a nil balance."]))
    assert out.decision == "FLAG_FOR_REVIEW" and out.triggers == ["GROUNDED_CONTRADICTION"]


def test_ungrounded_fraud_warning_is_shown_but_does_not_escalate():
    out = decide(gemini=gem("NEEDS_MORE_INFORMATION", ["Possible forged signature on an unseen document"]))
    assert out.decision == "NEEDS_MORE_INFORMATION" and out.unverified_concerns


@pytest.mark.parametrize("gemini_decision", ["FLAG_FOR_REVIEW", "REJECTED"])
def test_explicit_gemini_fraud_warning_escalates_but_never_auto_rejects(gemini_decision):
    out = decide(gemini=gem(gemini_decision, ["Ledger shows the fee was paid in full"]))
    assert out.decision == "FLAG_FOR_REVIEW" and out.triggers == ["GEMINI_EXPLICIT_FRAUD_WARNING"]


@pytest.mark.parametrize("v3", ["FLAG_FOR_REVIEW", "REJECTED"])
def test_v3_contradictions_are_preserved(v3):
    assert decide(v3=v3, gemini=gem("APPROVED")).decision == v3


@pytest.mark.parametrize("gemini", [None, gem(status="FAILED"), {"status": "OK", "decision": None}])
def test_gemini_failure_never_becomes_approval(gemini):
    out = decide(v3="APPROVED", gemini=gemini)
    assert out.decision == "VERIFICATION_ERROR" and out.workflow_state == "VERIFICATION_ERROR"


def test_both_approve_is_held_pending_confirmation_not_activated():
    out = decide(gemini=gem("APPROVED", missing=["Verified bank account"]))
    assert out.decision == "APPROVED" and out.workflow_state == "ELIGIBLE_PENDING_CONFIRMATION"


def test_gemini_approval_with_open_gaps_is_not_approved():
    out = decide(gemini=gem("APPROVED", ["Diagnosis not specified"]))
    assert out.decision == "NEEDS_MORE_INFORMATION" and out.triggers == ["UNRESOLVED_INFORMATION_GAP"]


def test_v3_information_request_is_not_overridden_by_gemini_approval():
    assert decide(v3="NEEDS_MORE_INFORMATION", gemini=gem("APPROVED")).decision == "NEEDS_MORE_INFORMATION"


def test_expired_and_future_dated_documents():
    expired = decide(gemini=gem("APPROVED"), docs=[("Quote", "Quotation valid until 01/09/2026")])
    future = decide(gemini=gem("APPROVED"), docs=[("Bill", "Bill dated 10 March 2027")])
    assert expired.decision == "NEEDS_MORE_INFORMATION" and expired.triggers == ["EXPIRED_DOCUMENT"]
    assert future.decision == "FLAG_FOR_REVIEW" and future.triggers == ["FUTURE_DATED_DOCUMENT"]


def test_spurious_model_future_date_claim_does_not_block_or_escalate():
    out = decide(gemini=gem("APPROVED", ["Ledger carries a future date (02 August 2026)"]))
    assert out.decision == "APPROVED" and out.vetoed_concerns


def test_exhaustive_never_approves_with_anything_unresolved():
    flag_sets = [(), ("Diagnosis not specified",), ("Story says the fee is unpaid, but the ledger shows a nil balance.",),
                 ("Possible forged signature on an unseen document",), ("Ledger carries a future date (02 August 2026)",)]
    v3s = ["APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR"]
    geminis = [None, "FAILED", "APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED"]
    docs = [None, [("Quote", "Quotation valid until 01/09/2026")], [("Bill", "Bill dated 10 March 2027")]]
    for v3, g, flags, d in itertools.product(v3s, geminis, flag_sets, docs):
        gemini = None if g is None else gem(status="FAILED") if g == "FAILED" else gem(g, flags)
        out = decide(v3=v3, gemini=gemini, docs=d)
        assert out.workflow_state != "VERIFIED_ACTIVE"
        if out.decision == "APPROVED":
            assert v3 == "APPROVED" and g == "APPROVED" and d is None
            assert flags in ((), ("Ledger carries a future date (02 August 2026)",))


# ----------------------------------------------------------------- client
CASE = {"title": "Semester fee", "category": "EDUCATION", "story": STORY, "goal_amount": 48500,
        "beneficiary_name": "Meera", "documents": [{"title": "Fee ledger"}]}


def response(payload):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}, "finishReason": "STOP"}]}


VALID = {"authenticity_score": 40, "risk_level": "HIGH", "recommendation": "FLAG_FOR_REVIEW", "summary": "s",
         "dimension_scores": {"plausibility": 1, "specificity": 1, "red_flag_score": 1, "documentation": 1},
         "red_flags": ["Fee already paid"], "positive_signals": [], "missing_requirements": [],
         "concerns": [{"category": "SUSPECTED_FRAUD", "description": "Fee already paid",
                       "evidence_quote": "paid in full on 02 August 2026"}]}


def call(transport, key="k"):
    return asyncio.run(verify_with_gemini(CASE, EVIDENCE, REF, date(2026, 10, 28), transport=transport, api_key=key))


def test_prompt_states_the_current_date_and_defines_future_dated():
    prompt = build_prompt(CASE, EVIDENCE, REF, date(2026, 10, 28))
    assert "30 October 2026 (2026-10-30)" in prompt and "28 October 2026" in prompt
    assert "NOT future-dated" in prompt and "evidence_quote" in prompt


def test_successful_response_is_parsed_with_structured_concerns():
    async def ok(*a, **k):
        return response(VALID)
    out = call(ok)
    assert out.status == "OK" and out.decision == "FLAG_FOR_REVIEW" and out.concerns[0]["category"] == "SUSPECTED_FRAUD"


@pytest.mark.parametrize("behaviour,category", [
    (GeminiAPIError("generation", "READ_TIMEOUT"), "READ_TIMEOUT"),
    (GeminiAPIError("generation", "SERVER_ERROR", 503), "SERVER_ERROR"),
    (GeminiAPIError("generation", "QUOTA_EXHAUSTED", 429), "QUOTA_EXHAUSTED"),
    ({"candidates": []}, "EMPTY_CANDIDATES"),
    ({"candidates": [{"finishReason": "MAX_TOKENS"}]}, "TRUNCATED_RESPONSE"),
    ({"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}, "JSON_PARSE_ERROR"),
    (response({"summary": "missing fields"}), "SCHEMA_VALIDATION"),
    (RuntimeError("boom"), "UNEXPECTED_RuntimeError"),
])
def test_every_failure_becomes_a_failed_outcome_never_an_exception(behaviour, category):
    async def transport(*a, **k):
        if isinstance(behaviour, Exception):
            raise behaviour
        return behaviour
    out = call(transport)
    assert out.status == "FAILED" and out.failure_category == category
    assert decide(gemini=out.model_dump()).decision == "VERIFICATION_ERROR"


def test_missing_key_fails_safely():
    assert call(None, key="").failure_category == "NOT_CONFIGURED"


def test_default_transport_keeps_production_retry_and_quota_protection(monkeypatch):
    import app.services.gemini_api as gemini_api
    seen = {}

    async def fake_post_json(url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        seen["max_attempts"] = max_attempts
        return response(VALID)
    monkeypatch.setattr(gemini_api, "post_json", fake_post_json)
    out = asyncio.run(verify_with_gemini(CASE, EVIDENCE, REF, transport=None, api_key="k"))
    assert out.status == "OK" and seen["max_attempts"] == 2


# ------------------------------------------------------------ production
def test_production_verifier_and_configuration_are_untouched():
    manifest = json.loads((ROOT / "evaluation/development_candidate_v3_freeze.json").read_text())
    for path, expected in manifest["production_file_sha256_at_freeze"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    assert "development_gemini_verification" not in (ROOT / "app/services/ai_verifier.py").read_text()


def test_unverified_fraud_concern_blocks_approval_without_escalating():
    out = decide(gemini=gem("APPROVED", ["Possible forged signature on an unseen document"]))
    assert out.decision == "NEEDS_MORE_INFORMATION" and out.triggers == ["UNRESOLVED_INFORMATION_GAP"]
    assert out.unverified_concerns
