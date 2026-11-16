"""Regression and behaviour tests for the development-only v2 verifier.

Documents below are hand-written in layouts that the v2 development-dataset
generator does not produce, so they exercise the extractor on unfamiliar text.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app.services.development_verifier_v2 import (
    CaseInput, Decision, DocumentInput, VerifierConfig, load_documents, verify_case,
)
from app.services.development_verifier_v2 import engine
from app.services.development_verifier_v2.money import find_amounts, parse_amount_field
from app.services.development_verifier_v2.normalize import (
    MATCH, MISMATCH, PARTIAL, compare_names, compare_orgs, find_dates, normalize_id,
)

ROOT = Path(__file__).resolve().parents[1]
SUBMITTED = date(2026, 10, 5)


def doc(title, text, doc_type="OTHER"):
    return DocumentInput(title=title, doc_type=doc_type, text=text)


def case(category, story, goal, documents, name=None, title="Help needed", beneficiary_type="SELF"):
    return CaseInput(title=title, category=category, story=story, goal_amount=goal, beneficiary_name=name,
                     beneficiary_type=beneficiary_type, submitted_on=SUBMITTED, documents=documents)


def codes(result):
    return {f.code for f in result.findings}


# ----------------------------------------------------------------- fixtures
HOSPITAL_ESTIMATE = """St. Mary's Hospital, Thrissur
Department of Gastroenterology & Hepatology

Cost Estimate No. SMH/EST/7781                     Date: 14/09/2026
Patient: Asha Verma          UHID: SMH/2026/00123          Age: 46
Consultant: Dr. Paul Varghese
Proposed procedure: liver transplant (deceased donor)

  Transplant surgery package          Rs. 18,50,000
  ICU and ward (21 days)              Rs.  6,20,000
  Post-operative drugs (3 months)     Rs.  3,30,000
Total estimate: Rs. 28,00,000/-
"""

HOSPITAL_SUMMARY = """St. Mary's Hospital - Hepatology clinic note
Date: 02 September 2026
Name: Asha Verma    UHID: SMH/2026/00123
Diagnosis: decompensated cirrhosis with recurrent ascites
Plan: evaluation completed; listed for liver transplant.
Dr. Paul Varghese, Consultant Hepatologist
"""

LIVER_STORY = ("Asha Verma, a 46-year-old schoolteacher from Thrissur, has end-stage liver disease. Doctors at "
               "St. Mary's Hospital have listed her for a liver transplant and estimate the cost at Rs 28 lakh.")


def liver_case(**overrides):
    documents = overrides.pop("documents", [doc("Cost estimate", HOSPITAL_ESTIMATE, "HOSPITAL_ESTIMATE"),
                                            doc("Clinic note", HOSPITAL_SUMMARY, "CLINICAL_NOTE")])
    params = dict(category="MEDICAL", story=LIVER_STORY, goal=2800000, documents=documents, name="Asha Verma",
                  title="Liver transplant for Asha")
    params.update(overrides)
    return case(**params)


FEE_NOTICE = """Government Polytechnic College, Kalamassery
Office of the Principal

FEE INTIMATION                                    Ref: GPC/FEE/2026/448
Dated 10.09.2026
Student: Rahul Menon, Roll No. EC-2025-117, Diploma in Electronics (2nd year)
Tuition fee            ₹18,500
Special fee            ₹4,200
Hostel (one term)      ₹21,300
Amount due: ₹44,000 on or before 30.10.2026.
Fees must be paid only at the college counter or through the college account.
"""

BONAFIDE = """Government Polytechnic College, Kalamassery
Date: 08-09-2026
This is to certify that Rahul Menon (Roll No. EC-2025-117) is a bonafide student of this college in the
second year of the Diploma in Electronics.
Principal
"""


def tuition_case(documents=None, goal=44000, story=None):
    story = story or ("Rahul Menon studies electronics at Government Polytechnic College, Kalamassery. His "
                      "father's shop flooded and the family cannot pay this term's fees of ₹44,000.")
    return case("EDUCATION", story, goal, documents if documents is not None else [
        doc("Fee intimation", FEE_NOTICE, "FEE_NOTICE"), doc("Bonafide certificate", BONAFIDE, "BONAFIDE")],
        name="Rahul Menon", title="Diploma fees for Rahul")


NGO_QUOTE = """Kaveri Solar Systems
Plot 12, Industrial Estate, Mandya

QUOTATION No. KSS/Q/219                Date: 18/09/2026
To: Hasiru Dala Mahila Sangha, Mandya
Work: supply and installation of solar street lights for the village lanes
  20 solar street lights (12 W)       2,40,000
  Poles, wiring and fixing            60,000
Total: Rs. 3,00,000
"""

NGO_REGISTRATION = """Office of the District Registrar of Societies, Mandya
Certificate of Registration
Hasiru Dala Mahila Sangha is registered as a society under the Karnataka Societies Registration Act, 1960.
Registration No.: MDY/SOC/2014/0071
President: Smt. Gowramma
"""


def ngo_case(documents=None, story=None, goal=300000):
    story = story or ("Hasiru Dala Mahila Sangha wants to light the dark lanes of our village so that women "
                      "returning from evening shifts are safe. The quotation for solar street lights is Rs 3 lakh.")
    return case("COMMUNITY", story, goal, documents if documents is not None else [
        doc("Solar light quotation", NGO_QUOTE, "QUOTATION"),
        doc("Society registration", NGO_REGISTRATION, "REGISTRATION")],
        name="Hasiru Dala Mahila Sangha", title="Solar lights for our village", beneficiary_type="ORGANISATION")


# ------------------------------------------------------------- 1. currency parsing
@pytest.mark.parametrize("text,expected", [
    ("₹2,45,000", 245000), ("Rs. 2,45,000/-", 245000), ("INR 4,20,000.00", 420000), ("Rs 245000", 245000),
    ("₹2.45 lakh", 245000), ("about 3 crore", 30000000), ("1,50,000 rupees", 150000), ("Rs.12,500.50", 12500.5),
    ("₹50k", 50000), ("the fee is Rs 75,000 for the term", 75000), ("Rs. 18,50,000", 1850000),
    ("2,45,000/-", 245000), ("₹ 1,00,000", 100000), ("12 lakhs", 1200000), ("Rs 4.5 lacs", 450000),
])
def test_rupee_amounts_are_parsed(text, expected):
    values = [m.value for m in find_amounts(text) if m.valid]
    assert values == [expected]


@pytest.mark.parametrize("text", [
    "mathematics and science papers, fee due", "teachers, 40 students", "UHID 88213 dated 12/03/2026",
    "Bill IB-1373", "Ward 11 (Tarapur): 230 households", "GBP 4,000.00", "hydrocortisone 100 mg twice daily",
    "Rs", "rs.", "The papers, 2026 edition", "users, 1,200 registered", "hours, 3", "drs, 12", "years, 2",
    "MRS 4", "Pairs, 4", "Report ID: MR1743", "Regn. No. MH/2019/0004000",
])
def test_non_monetary_text_yields_no_amounts(text):
    assert [m for m in find_amounts(text) if m.valid] == []


@pytest.mark.parametrize("text,issue", [("Rs.1,23,45", "MALFORMED_GROUPING"), ("₹1,2,3,4", "MALFORMED_GROUPING")])
def test_malformed_amounts_are_reported_not_raised(text, issue):
    mentions = find_amounts(text)
    assert mentions and not mentions[0].valid and mentions[0].issue == issue


@pytest.mark.parametrize("text,value,issue", [
    ("4,37,000", 437000, None), ("NIL (settled)", 0, None), ("2.5 lakh", 250000, None),
    ("12/03/2026", None, "NOT_AN_AMOUNT"), ("IB-1373", None, "NOT_AN_AMOUNT"), ("GBP 4,000.00", None, "FOREIGN_CURRENCY"),
    ("", None, "NOT_AN_AMOUNT"), ("papers,", None, "NOT_AN_AMOUNT"),
])
def test_amount_fields_are_validated(text, value, issue):
    parsed = parse_amount_field(text)
    assert parsed.value == value and parsed.issue == issue


def test_parser_never_raises_on_hostile_input():
    for text in ["rs,", "Rs.,", "₹,,,", "₹" + "9" * 400, "Rs. 1e9", "₹-500", "INR .", "\x00\xff₹1,0", "rupees,,"]:
        find_amounts(text)
        parse_amount_field(text)


def test_previously_crashing_education_cases_parse_without_error():
    """E150-095..098 crashed the v1 candidate: the 'rs' inside 'papers,' was read as a
    rupee marker.  They are used here only as crash regressions; the frozen
    independent benchmark is not used to tune decisions."""
    rows = [json.loads(line) for line in (ROOT / "evaluation/independent_test_150.jsonl").read_text().splitlines()]
    failing = [r for r in rows if r["case_id"] in {"E150-095", "E150-096", "E150-097", "E150-098"}]
    assert len(failing) == 4
    for row in failing:
        data = row["input"]
        result = verify_case(CaseInput(**{**data, "documents": [doc(d["title"], d["content"], d["doc_type"])
                                                               for d in data["documents"]]}))
        assert result.decision != Decision.VERIFICATION_ERROR and not result.errors
        amounts = [f for f in result.evidence[0].of("amount")]
        assert 8400.0 in [f.value for f in amounts] and all(f.value is not None for f in amounts)


# --------------------------------------------- 2. previously auto-approved fraud (IND-064 / IND-070)
@pytest.mark.parametrize("case_id", ["IND-064", "IND-070"])
def test_previously_auto_approved_fraud_is_not_approved(case_id):
    rows = [json.loads(line) for line in (ROOT / "evaluation/independent_benchmark_100.jsonl").read_text().splitlines()]
    data = next(r for r in rows if r["case_id"] == case_id)["input"]
    result = verify_case(CaseInput(**{**data, "documents": [doc(d["title"], d["content"], d["doc_type"])
                                                           for d in data["documents"]]}))
    assert result.decision not in {Decision.APPROVED, Decision.REJECTED, Decision.VERIFICATION_ERROR}


# ----------------------------------------------------- 3. legitimate cases and harmless variation
def test_legitimate_high_cost_treatment_is_approved_without_cost_alarm():
    result = verify_case(liver_case())
    assert result.decision == Decision.APPROVED, result.reasons
    assert not result.findings
    assert result.independent_verification == "UNAVAILABLE"
    assert any("not confirmed with the issuing" in note for note in result.uncertainty_notes)


def test_high_cost_without_documents_asks_for_information_not_review():
    result = verify_case(liver_case(documents=[]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION
    assert not any(f.severity.value == "material" for f in result.findings)


def test_harmless_name_date_amount_and_id_formatting_is_not_a_conflict():
    variant = (HOSPITAL_SUMMARY.replace("Name: Asha Verma", "Name: VERMA, ASHA")
               .replace("UHID: SMH/2026/00123", "UHID: smh-2026-123")
               .replace("02 September 2026", "2026-09-02")
               .replace("St. Mary's Hospital", "Saint Marys Hosp."))
    estimate = HOSPITAL_ESTIMATE.replace("Total estimate: Rs. 28,00,000/-", "Total estimate: ₹28 lakh")
    result = verify_case(liver_case(documents=[doc("Cost estimate", estimate), doc("Clinic note", variant)]))
    assert result.decision == Decision.APPROVED, [f.summary for f in result.findings]


@pytest.mark.parametrize("left,right,verdict", [
    ("Asha Verma", "VERMA, ASHA", MATCH), ("Asha Verma", "Smt. Asha Verma", MATCH),
    ("Asha Kumari Verma", "A. K. Verma", MATCH), ("Asha Kumari Verma", "Asha Verma", MATCH),
    ("Mohammed Irfan", "Mohd Irfan", MATCH), ("Asha Verma", "Asha Sharma", PARTIAL),
    ("Asha Verma", "Rekha Verma", MISMATCH), ("Asha Verma", "Dev Rao", MISMATCH),
    ("Lakshmi Iyer", "Laxmi Iyer", MATCH),
])
def test_name_comparison(left, right, verdict):
    assert compare_names(left, right)[0] == verdict


def test_known_limitation_nicknames_are_not_matched():
    # A pet name used in place of the registered given name cannot be linked
    # without outside information; it is reported as a mismatch (documented limitation).
    assert compare_names("Rajesh Kumar", "Bablu Kumar")[0] == MISMATCH


@pytest.mark.parametrize("left,right,verdict", [
    ("St. Mary's Hospital", "Saint Marys Hosp.", MATCH), ("Government Polytechnic College, Kalamassery",
                                                          "Govt. Polytechnic College Kalamassery", MATCH),
    ("Sahyadri Institute of Renal Sciences", "Lotus Kidney Care Hospital", MISMATCH),
])
def test_organisation_comparison(left, right, verdict):
    assert compare_orgs(left, right)[0] == verdict


def test_dates_and_identifiers_normalise():
    assert [d[0] for d in find_dates("02/09/2026, 2 Sep 2026, September 2, 2026, 2026-09-02, 31/02/2026")] == \
        [date(2026, 9, 2)] * 4
    assert normalize_id("SMH/2026/00123") == normalize_id("smh-2026-123")


def test_education_campaign_is_not_asked_for_medical_evidence():
    result = verify_case(tuition_case())
    assert result.decision == Decision.APPROVED, result.reasons
    assert {r.key for r in result.requirements} == {"cost_evidence", "enrolment_proof", "beneficiary_identity",
                                                    "institution_named"}


def test_registered_ngo_with_itemised_quote_is_approved():
    result = verify_case(ngo_case())
    assert result.decision == Decision.APPROVED, result.reasons


def test_partial_appeal_for_documented_balance_is_approved():
    notice = FEE_NOTICE.replace("Amount due: ₹44,000", "Scholarship adjusted: ₹14,000\nBalance due: ₹30,000")
    result = verify_case(tuition_case(documents=[doc("Fee intimation", notice), doc("Bonafide", BONAFIDE)], goal=30000))
    assert result.decision == Decision.APPROVED, [f.summary for f in result.findings]


# --------------------------------------------------------------- 4. contradictions
def test_contradictory_medical_records_are_flagged_with_provenance():
    summary = HOSPITAL_SUMMARY.replace("UHID: SMH/2026/00123", "UHID: SMH/2026/00988")
    result = verify_case(liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)]))
    assert result.decision == Decision.FLAG_FOR_REVIEW
    finding = next(f for f in result.findings if f.code == "IDENTIFIER_CONFLICT")
    assert {v.document for v in finding.values} == {"Cost estimate", "Clinic note"}
    assert all(v.chunk == 1 for v in finding.values) and 0 < finding.confidence <= 1 and finding.explanation


def test_records_for_another_patient_are_flagged():
    summary = HOSPITAL_SUMMARY.replace("Name: Asha Verma", "Name: Rekha Nair")
    result = verify_case(liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)]))
    assert result.decision == Decision.FLAG_FOR_REVIEW and "IDENTITY_MISMATCH" in codes(result)


def test_discharge_before_admission_is_flagged():
    record = ("Riverside General Hospital\nDischarge record\nName: Asha Verma\nAdmitted on 20/09/2026 and "
              "discharged on 12/09/2026 after a laparoscopic appendectomy.\nDr. N. Rao")
    result = verify_case(case("MEDICAL", "Asha Verma had emergency appendix surgery at Riverside General Hospital.",
                              90000, [doc("Bill", "Riverside General Hospital\nFinal bill dated 20/09/2026\n"
                                                  "Patient: Asha Verma\nTotal: Rs 90,000"),
                                      doc("Discharge record", record)], name="Asha Verma"))
    assert "DISCHARGE_BEFORE_ADMISSION" in codes(result) and result.decision == Decision.FLAG_FOR_REVIEW


def test_contradictory_fee_statements_are_flagged_but_a_later_revision_is_not():
    other = FEE_NOTICE.replace("Hostel (one term)      ₹21,300", "Hostel (one term)      ₹61,300") \
        .replace("Amount due: ₹44,000", "Amount due: ₹84,000").replace("GPC/FEE/2026/448", "GPC/FEE/2026/452")
    conflicting = verify_case(tuition_case(documents=[doc("Fee intimation A", FEE_NOTICE), doc("Fee intimation B", other),
                                                      doc("Bonafide", BONAFIDE)]))
    assert "COST_STATEMENTS_DISAGREE" in codes(conflicting)
    assert conflicting.decision == Decision.FLAG_FOR_REVIEW
    earlier = FEE_NOTICE.replace("Dated 10.09.2026", "Dated 01.07.2026").replace("₹44,000", "₹40,000")
    revised = verify_case(tuition_case(documents=[doc("Old notice", earlier), doc("Fee intimation", FEE_NOTICE),
                                                  doc("Bonafide", BONAFIDE)]))
    assert "COST_STATEMENTS_DISAGREE" not in codes(revised) and revised.decision == Decision.APPROVED


def test_fee_already_waived_is_flagged():
    notice = FEE_NOTICE.replace("Amount due: ₹44,000 on or before 30.10.2026.",
                                "The full fee has been waived under the e-Grantz scheme; balance due: NIL.")
    result = verify_case(tuition_case(documents=[doc("Fee intimation", notice), doc("Bonafide", BONAFIDE)]))
    assert result.decision == Decision.FLAG_FOR_REVIEW and "ALREADY_SETTLED" in codes(result)


def test_reimbursement_appeal_is_an_information_request_not_an_accusation():
    notice = FEE_NOTICE.replace("Amount due: ₹44,000 on or before 30.10.2026.", "Received with thanks: fee paid in full.")
    story = ("Rahul Menon's uncle borrowed ₹44,000 to pay this term's fees at Government Polytechnic College, "
             "Kalamassery, and we are raising money to repay that loan.")
    result = verify_case(tuition_case(documents=[doc("Fee receipt", notice), doc("Bonafide", BONAFIDE)], story=story))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION


def test_inconsistent_ngo_registration_numbers_are_flagged():
    letter = ("Mandya Rural Federation\nDate: 20/09/2026\nCertified that Hasiru Dala Mahila Sangha, Regd. No. "
              "MDY/SOC/2019/0444, is a member organisation in good standing.\nCoordinator")
    result = verify_case(ngo_case(documents=[doc("Quotation", NGO_QUOTE), doc("Registration", NGO_REGISTRATION),
                                             doc("Federation letter", letter)]))
    assert "IDENTIFIER_CONFLICT" in codes(result) and result.decision == Decision.FLAG_FOR_REVIEW


def test_cancelled_ngo_registration_is_flagged():
    cancelled = NGO_REGISTRATION + "Remarks: registration cancelled for failure to file annual returns.\n"
    result = verify_case(ngo_case(documents=[doc("Quotation", NGO_QUOTE), doc("Registration", cancelled)]))
    assert "STATUS_REVOKED" in codes(result) and result.decision == Decision.FLAG_FOR_REVIEW


def test_quotation_for_different_work_is_flagged():
    other_work = NGO_QUOTE.replace("supply and installation of solar street lights for the village lanes",
                                   "supply of cricket kits and team jerseys")
    result = verify_case(ngo_case(documents=[doc("Quotation", other_work), doc("Registration", NGO_REGISTRATION)]))
    assert result.decision == Decision.FLAG_FOR_REVIEW and any(f.kind == "service" for f in result.findings)


def test_inflated_request_is_flagged_and_modest_excess_asks_for_information():
    inflated = verify_case(ngo_case(goal=750000))
    modest = verify_case(ngo_case(goal=330000 + 20000))
    assert inflated.decision == Decision.FLAG_FOR_REVIEW
    assert modest.decision == Decision.NEEDS_MORE_INFORMATION


def test_third_party_payee_is_flagged_but_institution_payee_is_not():
    diverted = FEE_NOTICE.replace("Fees must be paid only at the college counter or through the college account.",
                                  "Kindly transfer the fee to account holder: Suresh Pillai, SB A/c 99120033.")
    result = verify_case(tuition_case(documents=[doc("Fee intimation", diverted), doc("Bonafide", BONAFIDE)]))
    assert "THIRD_PARTY_PAYEE" in codes(result)
    assert "THIRD_PARTY_PAYEE" not in codes(verify_case(tuition_case()))


def test_off_platform_solicitation_without_scam_keywords_is_flagged():
    story = ("Rahul Menon studies electronics at Government Polytechnic College, Kalamassery. Please send "
             "your contribution straight to my brother's PhonePe number so it reaches us faster.")
    result = verify_case(tuition_case(story=story))
    assert "OFF_PLATFORM_SOLICITATION" in codes(result)


# --------------------------------------------------- 5. missing / ambiguous / malformed evidence
def test_missing_documents_request_information_and_never_reject():
    for factory in (liver_case, tuition_case, ngo_case):
        result = verify_case(factory(documents=[]))
        assert result.decision == Decision.NEEDS_MORE_INFORMATION
        assert result.information_requests
        assert any("not evidence of fraud" in reason for reason in result.reasons)


def test_provisional_estimate_requires_human_follow_up_not_fraud_flag():
    provisional = HOSPITAL_ESTIMATE + "PROVISIONAL: donor allocation awaited; this estimate is not final.\n"
    result = verify_case(liver_case(documents=[doc("Cost estimate", provisional), doc("Clinic note", HOSPITAL_SUMMARY)]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION


def test_partial_name_match_is_ambiguous():
    summary = HOSPITAL_SUMMARY.replace("Name: Asha Verma", "Name: Asha Sharma")
    result = verify_case(liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION and "IDENTITY_UNCERTAIN" in codes(result)


def test_unattributable_note_is_not_sufficient_evidence():
    note = doc("Cost note", "Liver transplant for Asha Verma will cost Rs 28,00,000 in total. Please help.")
    result = verify_case(liver_case(documents=[note]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION


def test_binary_or_garbage_document_is_unreadable_not_an_error():
    garbage = doc("Scan", "\x00\x01\x02%PDF-1.4 ÿÿÿ \x7f\x7f" * 3)
    result = verify_case(liver_case(documents=[garbage]))
    assert result.decision == Decision.NEEDS_MORE_INFORMATION
    assert "UNREADABLE_DOCUMENT" in codes(result)


def test_malformed_amount_in_document_is_controlled():
    broken = HOSPITAL_ESTIMATE.replace("Rs. 28,00,000/-", "Rs.28,00,00,0")
    result = verify_case(liver_case(documents=[doc("Cost estimate", broken), doc("Clinic note", HOSPITAL_SUMMARY)]))
    assert result.decision != Decision.VERIFICATION_ERROR
    assert "MALFORMED_AMOUNT" in result.evidence[0].issues


# ------------------------------------------------- 6. failures can never become approvals
def test_missing_file_is_a_retrieval_failure(tmp_path):
    (tmp_path / "estimate.txt").write_text(HOSPITAL_ESTIMATE, encoding="utf-8")
    references = [{"title": "Cost estimate", "file_url": "/private-documents/estimate.txt"},
                  {"title": "Clinic note", "file_url": "/private-documents/missing.txt"},
                  {"title": "Escape", "file_url": "/private-documents/../../etc/passwd"}]
    documents = load_documents(references, tmp_path)
    assert documents[0].text and documents[1].load_error == "FILE_NOT_FOUND" and documents[2].load_error
    result = verify_case(liver_case(documents=documents))
    assert result.decision == Decision.VERIFICATION_ERROR
    assert result.decision != Decision.APPROVED


def test_extractor_exception_is_a_retrieval_failure(tmp_path):
    (tmp_path / "scan.pdf").write_bytes(b"%PDF-1.4 broken")

    def broken_extractor(path):
        raise RuntimeError("corrupt xref table")

    documents = load_documents([{"title": "Scan", "file_url": "scan.pdf"}], tmp_path, extractor=broken_extractor)
    assert documents[0].load_error == "EXTRACTION_FAILED_RuntimeError"
    assert verify_case(liver_case(documents=documents)).decision == Decision.VERIFICATION_ERROR


def test_external_reasoner_api_failure_blocks_approval():
    def gemini_cross_check(ctx):
        raise TimeoutError("simulated Gemini timeout")

    baseline = verify_case(liver_case())
    failed = verify_case(liver_case(), reasoners=[gemini_cross_check])
    assert baseline.decision == Decision.APPROVED
    assert failed.decision == Decision.VERIFICATION_ERROR
    assert any("TimeoutError" in error for error in failed.errors)
    assert not failed.positive_signals


@pytest.mark.parametrize("stage", ["check_identity", "check_amounts", "check_service", "detect_settlement"])
def test_any_stage_exception_prevents_approval(monkeypatch, stage):
    from app.services.development_verifier_v2 import consistency, semantic

    def boom(ctx):
        raise ValueError("invalid literal for int() with base 10: ''")

    monkeypatch.setattr(engine, "CHECKS", [boom if c.__name__ == stage else c for c in consistency.CHECKS])
    monkeypatch.setattr(engine, "SIGNALS", [boom if s.__name__ == stage else s for s in semantic.SIGNALS])
    result = verify_case(liver_case())
    assert result.decision == Decision.VERIFICATION_ERROR
    assert result.audit.errors


def test_extraction_crash_prevents_approval(monkeypatch):
    monkeypatch.setattr(engine, "extract_document", lambda *a: (_ for _ in ()).throw(KeyError("x")))
    assert verify_case(liver_case()).decision == Decision.VERIFICATION_ERROR


def test_material_finding_survives_a_partial_failure():
    summary = HOSPITAL_SUMMARY.replace("Name: Asha Verma", "Name: Rekha Nair")

    def flaky(ctx):
        raise ConnectionError("network")

    result = verify_case(liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)]),
                         reasoners=[flaky])
    assert result.decision == Decision.FLAG_FOR_REVIEW
    assert any("incomplete" in reason for reason in result.reasons)


# --------------------------------------------------------- 7. decision policy
def test_rejection_needs_two_independent_strong_findings():
    summary = HOSPITAL_SUMMARY.replace("Name: Asha Verma", "Name: Rekha Nair")
    settled = HOSPITAL_ESTIMATE + "Payment status: paid in full by the Karunya Benevolent Fund; no amount is due.\n"
    one = verify_case(liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)]))
    two = verify_case(liver_case(documents=[doc("Cost estimate", settled), doc("Clinic note", summary)]))
    assert one.decision == Decision.FLAG_FOR_REVIEW
    assert two.decision == Decision.REJECTED
    assert set(two.influencing_dimensions) >= {"identity", "financial"}


def test_every_decision_has_reasons_dimensions_and_scores():
    for result in (verify_case(liver_case()), verify_case(liver_case(documents=[])), verify_case(ngo_case(goal=750000))):
        assert result.reasons and result.influencing_dimensions
        assert set(result.dimension_scores) == {"identity", "financial", "institutional", "narrative", "documentation"}
        assert 0 <= result.authenticity_score <= 100


def test_ablation_switches_disable_components():
    summary = HOSPITAL_SUMMARY.replace("Name: Asha Verma", "Name: Rekha Nair")
    mismatched = liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)])
    assert verify_case(mismatched, VerifierConfig(enable_cross_document=False)).decision != Decision.FLAG_FOR_REVIEW
    no_category = verify_case(tuition_case(), VerifierConfig(enable_category=False))
    assert [r.key for r in no_category.requirements] == ["cost_evidence"]


# ------------------------------------------------------------- 8. audit privacy
def test_audit_record_contains_no_private_details(caplog):
    summary = HOSPITAL_SUMMARY.replace("UHID: SMH/2026/00123", "UHID: SMH/2026/00988")
    with caplog.at_level("INFO", logger="sevafund.development_verifier_v2.audit"):
        result = verify_case(liver_case(documents=[doc("Cost estimate", HOSPITAL_ESTIMATE), doc("Clinic note", summary)]))
    logged = json.dumps(result.audit.model_dump()) + caplog.text
    for secret in ("Asha", "Verma", "SMH2026", "00988", "00123", "schoolteacher", "Varghese", "Clinic note"):
        assert secret not in logged
    assert result.audit.decision == "FLAG_FOR_REVIEW" and result.audit.findings[0]["code"]
    assert "IDENTIFIER_CONFLICT" in result.audit.reason_codes
    assert {v["document"] for v in result.audit.findings[0]["values"]} == {"document#1", "document#2"}
    assert any(stage["stage"] == "extraction" for stage in result.audit.stages)


def test_audit_omits_uploader_titles_that_contain_names():
    named = liver_case(documents=[doc("Asha Verma bill", HOSPITAL_ESTIMATE), doc("Asha Verma notes", HOSPITAL_SUMMARY)])
    result = verify_case(named)
    assert "Asha" not in json.dumps(result.audit.model_dump())


def test_decision_never_approves_without_evaluated_requirements():
    from app.services.development_verifier_v2.decision import decide
    assert decide([], [], [], VerifierConfig(), document_count=2).decision == Decision.NEEDS_MORE_INFORMATION
