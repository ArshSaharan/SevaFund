"""Regression coverage for the isolated SevaFund V3 verifier."""
from decimal import Decimal

import pytest
import json
from pathlib import Path

try:
    from app.services.development_verifier_v3.money import (
        MoneyMention, find_amounts, parse_amount_field, compare_amounts,
    )
except ImportError:  # V3 is introduced test-first; turn a missing module into assertions.
    MoneyMention = find_amounts = parse_amount_field = compare_amounts = None


def require_parser():
    assert MoneyMention is not None, "V3 money parser module is not implemented"
    assert callable(find_amounts), "find_amounts must be callable"
    assert callable(parse_amount_field), "parse_amount_field must be callable"
    assert callable(compare_amounts), "compare_amounts must be callable"


@pytest.mark.parametrize("text,amount,currency", [
    ("₹2,45,000", "245000", "INR"),
    ("Rs. 2,45,000/-", "245000", "INR"),
    ("INR 4,20,000.25", "420000.25", "INR"),
    ("USD 1,250.75", "1250.75", "USD"),
    ("$1,250.75", "1250.75", "USD"),
    ("GBP 4,000.00", "4000.00", "GBP"),
    ("£4,000", "4000", "GBP"),
    ("EUR 2.750,50", "2750.50", "EUR"),
    ("₹1.25 lakh", "125000", "INR"),
    ("2.4 crore rupees", "24000000", "INR"),
    ("tuition fees: 38,500 due this term", "38500", "INR"),
    ("hospital estimate, amount payable 7.25 lakh", "725000", "INR"),
    ("rupees fifty thousand", "50000", "INR"),
    ("USD one thousand two hundred dollars", "1200", "USD"),
])
def test_currency_amount_formats_are_typed_as_decimal(text, amount, currency):
    require_parser()
    mentions = find_amounts(text)
    assert len(mentions) == 1
    assert mentions[0].valid
    assert mentions[0].amount == Decimal(amount)
    assert mentions[0].currency == currency


@pytest.mark.parametrize("text", [
    "mathematics and science papers, fee due",
    "teachers, 40 students",
    "UHID 88213 dated 12/03/2026",
    "Bill IB-1373",
    "Ward 11 (Tarapur): 230 households",
    "The papers, 2026 edition",
    "users, 1,200 registered",
    "Tuition fee covers 2 students for the term",
    "MRS 4", "MRS. Rao", "years, 2", "drs, 12",
    "Date 12/03/2026; roll number 2026-2027; account 00401234",
])
def test_non_money_words_dates_and_identifiers_are_not_amounts(text):
    require_parser()
    assert find_amounts(text) == []


@pytest.mark.parametrize("text,issue", [
    ("₹1,23,45", "MALFORMED_GROUPING"),
    ("₹1,2,3,4", "MALFORMED_GROUPING"),
    ("GBP 4,00,0.2", "MALFORMED_GROUPING"),
    ("₹" + "9" * 80, "OUT_OF_RANGE"),
])
def test_malformed_monetary_inputs_are_explicit_and_never_raise(text, issue):
    require_parser()
    mention = find_amounts(text)[0]
    assert not mention.valid
    assert mention.issue == issue
    assert mention.amount is None


def test_currency_compare_never_converts_without_verified_rate():
    require_parser()
    inr = parse_amount_field("₹100,000")
    usd = parse_amount_field("USD 1,200")
    gbp = parse_amount_field("GBP 800")
    assert compare_amounts(inr, usd) is None
    assert compare_amounts(usd, gbp) is None
    assert compare_amounts(inr, parse_amount_field("INR 99,000")) == Decimal("1000")


def test_bare_numbers_need_monetary_field_context():
    require_parser()
    assert parse_amount_field("38,500", currency_context="tuition fee").currency == "INR"
    assert not parse_amount_field("12/03/2026", currency_context="document date").valid
    assert not parse_amount_field("IB-1373", currency_context="invoice reference").valid
    assert not parse_amount_field("", currency_context="amount due").valid


from app.services.development_verifier_v3 import CaseInput, Decision, DocumentInput, verify_case
from app.services.development_verifier_v3.config import DEFAULT_CONFIG
from app.services.development_verifier_v3.decision import decide
from app.services.development_verifier_v3.schemas import Finding, Severity


def case_with_docs(story, documents, **extra):
    payload = dict(title="Medical support request", category="MEDICAL", story=story,
                   goal_amount=85000, beneficiary_name="Maya Iyer", documents=documents)
    payload.update(extra)
    return CaseInput(**payload)


def sufficient_medical_cost_doc(amount="₹85,000", patient="Maya Iyer"):
    return DocumentInput(doc_type="HOSPITAL_ESTIMATE", title="Harborview hospital estimate",
                         text=("Harborview Medical Hospital\n"
                               f"Patient Name: {patient}\n"
                               "Estimate reference: HMH-2026-402\n"
                               "Date: 10 October 2026\n"
                               f"Total treatment estimate: {amount}\n"
                               "Consultant: Dr Leena Das"))


def test_optional_clinical_and_itemisation_gaps_do_not_request_more_information():
    result = verify_case(case_with_docs("Treatment costs are requested for Maya's care.",
                                        [sufficient_medical_cost_doc()]))
    assert result.decision == Decision.APPROVED, result.reasons
    assert result.information_requests == []
    assert any(r.key == "clinical_detail" and not r.satisfied and not r.critical for r in result.requirements)


def test_missing_critical_identity_or_claim_evidence_requests_information():
    doc = DocumentInput(doc_type="HOSPITAL_ESTIMATE", title="Unlinked estimate",
                        text="Harborview Medical Hospital estimate reference HMH-402. Total treatment estimate ₹85,000.")
    result = verify_case(case_with_docs("Treatment costs are requested for Maya's care.", [doc]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION, result.errors + result.reasons
    assert any("beneficiary identity" in request.lower() for request in result.information_requests)


def test_unverified_foreign_exchange_rate_is_never_used_for_comparison():
    result = verify_case(case_with_docs("Treatment costs are requested for Maya's care.",
                                        [sufficient_medical_cost_doc("USD 1,250")]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION
    assert any(f.code == "CURRENCY_NOT_COMPARABLE" for f in result.findings)


def test_explicit_malformed_financial_amount_cannot_silently_approve():
    result = verify_case(case_with_docs("Treatment costs are requested for Maya's care.",
                                        [sufficient_medical_cost_doc("₹1,23,45")]))
    assert result.decision == Decision.VERIFICATION_ERROR
    assert "AMOUNT_PARSE_INVALID" in result.errors


@pytest.mark.parametrize("title,story,document,code", [
    ("Twelve month instruction appeal", "The request covers twelve months of instruction.",
     "Marina Skills Institute. Ten instructional weeks; no additional term is scheduled.",
     "CAMPAIGN_DOCUMENT_DURATION_CONFLICT"),
    ("Forty book sets for a rural classroom", "The purchase request lists 40 book sets.",
     "Delivery record: 24 book sets were handed to the school librarian.",
     "CAMPAIGN_DOCUMENT_QUANTITY_CONFLICT"),
])
def test_cross_document_quantities_and_periods_are_compared_as_evidence(title, story, document, code):
    result = verify_case(CaseInput(
        title=title, category="EDUCATION", story=story, goal_amount=55000,
        documents=[DocumentInput(title="Institute or delivery record", doc_type="SUPPORT", text=document)]))
    assert any(f.code == code and f.component == "cross_document" for f in result.findings), result.errors + result.reasons
    assert result.decision == Decision.FLAG_FOR_REVIEW, result.errors + result.reasons


def test_one_contradiction_flags_review_but_does_not_reject():
    finding = Finding(kind="identity", code="ID_CONFLICT", dimension="identity", component="cross_document",
                      severity=Severity.MATERIAL, confidence=0.95, summary="Identity differs.",
                      explanation="The source records a different person.")
    result = decide([finding], [], [], DEFAULT_CONFIG, document_count=1)
    assert result.decision == Decision.FLAG_FOR_REVIEW


def test_rejection_requires_independent_high_confidence_dimensions():
    findings = [Finding(kind="identity", code="ID_CONFLICT", dimension="identity", component="cross_document",
                        severity=Severity.MATERIAL, confidence=0.95, summary="Identity differs.", explanation="Mismatch."),
                Finding(kind="amount", code="MONEY_CONFLICT", dimension="financial", component="cross_document",
                        severity=Severity.MATERIAL, confidence=0.92, summary="Amounts differ.", explanation="Mismatch.")]
    result = decide(findings, [], [], DEFAULT_CONFIG, document_count=2)
    assert result.decision == Decision.REJECTED


def test_stage_error_can_never_turn_into_approval():
    result = decide([], [], ["AMOUNT_PARSE_INVALID"], DEFAULT_CONFIG, document_count=1)
    assert result.decision == Decision.VERIFICATION_ERROR


def test_unrelated_document_payee_is_flagged_for_manual_review():
    payout = DocumentInput(doc_type="BANK_INSTRUCTION", title="Payment routing note",
                           text="Harborview Medical Hospital billing note. Account holder: Vikram Sen. "
                                "Settlement proceeds are directed to the named account, not to the patient.")
    result = verify_case(case_with_docs("Treatment costs are requested for Maya's care.",
                                        [sufficient_medical_cost_doc(), payout]))
    assert any(f.code == "THIRD_PARTY_PAYEE" for f in result.findings)
    assert result.decision == Decision.FLAG_FOR_REVIEW


def test_document_agreement_is_not_reported_as_independent_authentication():
    result = verify_case(case_with_docs("Treatment costs are requested for Maya's care.",
                                        [sufficient_medical_cost_doc(),
                                         DocumentInput(doc_type="CLINICAL_NOTE", title="Follow-up note",
                                                       text="Harborview Medical Hospital. Patient Maya Iyer. "
                                                            "The follow-up plan is recorded in the clinic file.")]))
    assert result.independent_verification == "UNAVAILABLE"
    assert any("not independently authenticated" in note.lower() for note in result.uncertainty_notes)


@pytest.mark.parametrize("case_id", ["IND-064", "IND-070"])
def test_historic_contradiction_cases_are_regression_only_and_never_approved(case_id):
    path = Path(__file__).resolve().parents[1] / "evaluation" / "independent_benchmark_100.jsonl"
    row = next(json.loads(line) for line in path.read_text().splitlines()
               if json.loads(line)["case_id"] == case_id)
    data = row["input"]
    result = verify_case(CaseInput(**{**data, "documents": [DocumentInput(
        title=item["title"], doc_type=item["doc_type"], text=item["content"])
        for item in data["documents"]]}))
    assert result.decision != Decision.APPROVED
    assert result.decision != Decision.REJECTED
    assert result.decision != Decision.VERIFICATION_ERROR
