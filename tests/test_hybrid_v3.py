"""Regression tests for hybrid v3 (development only, no network).

New scenario texts written for these tests (not the DA evaluation texts) cover legitimate, fraudulent, borderline
and incomplete-document cases; the DA cases are re-checked at the end as development regressions.
"""
import itertools
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.development_approval_workflow.schemas import (ConfirmationCheck, ConfirmationOutcome,
                                                                ConfirmationRecord, ContactSource, WorkflowState)
from app.services.development_approval_workflow.workflow import (IllegalTransition, record_confirmation,
                                                                 reviewer_resolution)
from app.services.development_hybrid_v3 import (GEMINI_DEPENDENT, activation_status, assess, assess_case,
                                                 is_financial, start_record)
from app.services.development_hybrid_v3.dates import assess_text

ROOT = Path(__file__).resolve().parents[1]
REF = date(2026, 11, 17)
APPROVE = {"status": "OK", "decision": "APPROVED", "concerns": [], "red_flag_texts": [], "missing_requirements": []}
FAILED = {"status": "FAILED", "failure_category": "SERVER_ERROR"}
INFO_UNGROUNDED = {"status": "OK", "decision": "NEEDS_MORE_INFORMATION", "red_flag_texts": [], "missing_requirements": [],
                   "concerns": [{"category": "SUSPECTED_FRAUD", "description": "The paperwork might be forged.", "evidence_quote": ""}]}
APPROVE_UNGROUNDED = dict(INFO_UNGROUNDED, decision="APPROVED")
FLAG_UNGROUNDED = dict(INFO_UNGROUNDED, decision="FLAG_FOR_REVIEW")
REJECT_UNGROUNDED = dict(INFO_UNGROUNDED, decision="REJECTED")
GEMINI_OUTPUTS = [APPROVE, FAILED, INFO_UNGROUNDED, APPROVE_UNGROUNDED, FLAG_UNGROUNDED, REJECT_UNGROUNDED]


def d(offset: int, style: str = "dmy") -> str:
    value = REF + timedelta(days=offset)
    return value.strftime("%d/%m/%Y") if style == "dmy" else f"{value.day} {value.strftime('%B %Y')}"


def doc(title, doc_type, content):
    return {"title": title, "doc_type": doc_type, "content": content}


def case(title, category, story, goal, name, documents, beneficiary_type="SELF"):
    return {"title": title, "category": category, "story": story, "goal_amount": goal, "goal_currency": "INR",
            "beneficiary_name": name, "beneficiary_type": beneficiary_type, "city": "Pune", "state": "Maharashtra",
            "submitted_on": REF.isoformat(), "documents": documents}


def chunks(c):
    return [{"title": x["title"], "doc_type": x["doc_type"], "text": x["content"], "relevance": 1.0} for x in c["documents"]]


def run(c, gemini=APPROVE):
    return assess_case(c, gemini, chunks(c), REF)


# ------------------------------------------------------------------ fixtures
BONAFIDE = doc("School letter", "ENROLMENT_RECORD",
               f"Government Girls High School, Kohima\nLetter No. GGHS/88, dated {d(-10)}\nThis is to certify that Neikhrienuo "
               f"Angami is a bonafide student of Class X. Her fees for the year come to about Rs 45,000.\nHeadmaster")
QUOTE = doc("Supplier quotation", "SUPPLIER_QUOTE",
            f"Lumbini Learning Supplies, Dimapur\nQuotation No. LLS/Q/221, Date: {d(-6)}\nTo: Neikhrienuo Angami. Class X "
            f"textbooks Rs 21,500; scientific calculator Rs 2,000; tuition fee for the year Rs 21,500. Total: Rs 45,000. "
            f"Quotation valid for 30 days.\nAuthorised signatory")


def education(documents, goal=45000):
    return case("Class X fees and books for Neikhrienuo Angami", "EDUCATION",
                "Neikhrienuo Angami is a Class X student at Government Girls High School, Kohima. Her father is a daily "
                f"wage worker. We need Rs {goal:,} for her fees and books this year.", goal, "Neikhrienuo Angami", documents)


def medical_bill(story_discharge=-5, bill_balance="Rs 1,12,000", extra=()):
    return case("ICU bill for Farhan Qureshi", "MEDICAL",
                f"My brother Farhan Qureshi, 34, was admitted to Indus Valley Hospital, Pune with pneumonia on {d(-20, 'long')}. "
                f"He was discharged on {d(story_discharge, 'long')} and we must clear the bill of Rs 1,12,000.",
                112000, "Farhan Qureshi",
                [doc("Discharge summary", "DISCHARGE_SUMMARY",
                     f"Indus Valley Hospital, Pune\nDischarge Summary, dated {d(-5)}\nPatient: Farhan Qureshi, 34 M, UHID IVH-55120.\n"
                     f"Date of admission: {d(-20)}. Diagnosis: community-acquired pneumonia. Discharged on {d(-5)} in stable condition."),
                 doc("Final bill", "FINAL_BILL",
                     f"Indus Valley Hospital, Pune\nBill No. IVH/FB/901, Bill date: {d(-5)}\nPatient: Farhan Qureshi, UHID IVH-55120. "
                     f"Ward Rs 52,000; ICU Rs 40,000; pharmacy Rs 20,000. Balance payable: {bill_balance}."), *extra])


# ------------------------------------------------------------------ 1. financial evidence (DA-07)
def test_school_letter_alone_never_establishes_the_amount():
    c = education([BONAFIDE])
    assert not is_financial(BONAFIDE["title"], BONAFIDE["doc_type"], BONAFIDE["content"])
    for gemini in GEMINI_OUTPUTS:
        out = run(c, gemini)
        assert out.decision != "APPROVED"
        assert out.financial_evidence["status"] == "MISSING"
    out = run(c, APPROVE)
    assert out.decision == "NEEDS_MORE_INFORMATION" and out.triggers == ["FINANCIAL_EVIDENCE_MISSING"]
    assert any("does not establish the amount" in r for r in out.information_requests)


def test_a_traceable_current_quotation_establishes_the_amount():
    out = run(education([BONAFIDE, QUOTE]))
    assert out.financial_evidence["status"] == "SUPPORTED" and out.financial_evidence["documented_need"] == 45000
    assert out.decision == "APPROVED" and out.workflow_state == "ELIGIBLE_PENDING_CONFIRMATION"


@pytest.mark.parametrize("goal,status", [(46000, "SUPPORTED"), (47250, "SUPPORTED"), (52000, "INSUFFICIENT_AMOUNT")])
def test_goal_tolerance_is_five_percent(goal, status):
    out = run(education([BONAFIDE, QUOTE], goal=goal))
    assert out.financial_evidence["status"] == status
    if status != "SUPPORTED":
        assert out.decision != "APPROVED"


def test_expired_quotation_is_an_information_request():
    stale = doc("Supplier quotation", "SUPPLIER_QUOTE", QUOTE["content"].replace(f"Date: {d(-6)}", f"Date: {d(-90)}"))
    out = run(education([BONAFIDE, stale]))
    assert out.financial_evidence["status"] == "EXPIRED" and out.decision == "NEEDS_MORE_INFORMATION"


def test_untraceable_quotation_is_an_information_request():
    bare = doc("Quotation", "SUPPLIER_QUOTE", "Quotation for textbooks Rs 21,500; scientific calculator Rs 2,000; annual "
                                              "tuition fee Rs 21,500. Total Rs 45,000.")       # no issuer, date or reference
    out = run(education([BONAFIDE, bare]))
    assert out.financial_evidence["status"] == "UNTRACEABLE" and out.decision == "NEEDS_MORE_INFORMATION"


def test_an_order_with_a_total_counts_but_a_sentence_mentioning_an_estimate_does_not():
    order = "Riverside Mobility Clinic\nPatient: X\nEquipment order RMC-12; 02 November 2026. Walker and fitting: total Rs 9,000."
    plan = "Riverside Mobility Clinic\nPatient: X\nThe travel desk's combined estimate is Rs 9,000 for the visits."
    assert is_financial("Home device schedule", "EQUIPMENT_PLAN", order)
    assert not is_financial("Attendance plan", "REHAB_SCHEDULE", plan)


# ------------------------------------------------------------------ 2. cross-document contradictions (DA-05)
def _memorial(certificate_offset):
    return case("Hospital dues after the death of Gopal Iyer", "MEDICAL",
                f"My uncle Gopal Iyer died on {d(-4, 'long')} in the ICU of Cauvery Care Hospital. The hospital asks us to "
                "settle Rs 96,000 before releasing his body.", 96000, "Gopal Iyer",
                [doc("Hospital bill", "FINAL_BILL", f"Cauvery Care Hospital, Tiruchirappalli\nBill No. CCH/771, Bill date: {d(-3)}\n"
                     f"Patient: Gopal Iyer, 71 M. ICU Rs 70,000; medicines Rs 26,000. Outstanding: Rs 96,000."),
                 doc("Death certificate", "REGISTRATION_EXTRACT", f"Tiruchirappalli Municipal Corporation\nDeath Certificate, "
                     f"date of registration: {d(certificate_offset + 2)}\nName of deceased: Gopal Iyer, male, age 71. "
                     f"Date of death: {d(certificate_offset)}.")], "FAMILY")


@pytest.mark.parametrize("gemini", GEMINI_OUTPUTS)
def test_conflicting_death_dates_are_reviewed_whatever_gemini_says(gemini):
    out = run(_memorial(-150), gemini)
    assert out.decision == "FLAG_FOR_REVIEW" and out.review_basis == "DETERMINISTIC_FINDING"
    assert "DEATH_DATE_CONFLICT" in out.triggers[0]


def test_death_dates_one_day_apart_are_not_a_contradiction():
    out = run(_memorial(-5))
    assert not [f for f in out.cross_document_findings if f["code"] == "DEATH_DATE_CONFLICT"]


def test_story_discharge_date_contradicted_by_the_record():
    out = run(medical_bill(story_discharge=-60))
    assert out.decision == "FLAG_FOR_REVIEW" and "EVENT_DATE_CONFLICT" in out.triggers[0]
    assert not run(medical_bill(story_discharge=-6)).cross_document_findings      # within tolerance


def test_patient_identifier_conflict():
    lab = doc("Lab report", "MEDICAL_REPORT", f"Indus Valley Hospital Laboratory\nReport date: {d(-18)}\n"
                                              "Patient: Farhan Qureshi, 34 M, UHID IVH-90311. Chest X-ray: right lower lobe consolidation.")
    out = run(medical_bill(extra=[lab]))
    assert out.decision == "FLAG_FOR_REVIEW"                     # frozen V3 (IDENTIFIER_CONFLICT) also catches this one
    assert "PATIENT_ID_CONFLICT" in {f["code"] for f in out.cross_document_findings}


def test_identifier_of_a_different_person_is_not_compared():
    other = doc("Attendant pass", "OTHER", f"Indus Valley Hospital\nDate: {d(-19)}\nAttendant: Salma Qureshi, UHID IVH-12345.")
    assert not run(medical_bill(extra=[other])).cross_document_findings


@pytest.mark.parametrize("age,conflict", [("35 M", False), ("43 M", True), ("34 F", True)])
def test_age_and_sex_conflicts(age, conflict):
    lab = doc("Lab report", "MEDICAL_REPORT", f"Indus Valley Hospital Laboratory\nReport date: {d(-18)}\n"
                                              f"Patient: Farhan Qureshi, {age}, UHID IVH-55120. Sputum culture: no growth.")
    codes = {f["code"] for f in run(medical_bill(extra=[lab])).cross_document_findings}
    assert bool(codes & {"AGE_CONFLICT", "SEX_CONFLICT"}) == conflict


def _cardiac(note):
    return case("Heart surgery for Meera Pillai", "MEDICAL",
                "Meera Pillai, 58, needs valve replacement surgery at Malabar Heart Centre. The surgery costs Rs 3,20,000.",
                320000, "Meera Pillai",
                [doc("Cardiology note", "CLINICAL_NOTE", f"Malabar Heart Centre, Kozhikode\nDate: {d(-12)}\n"
                     f"Patient: Meera Pillai, 58 F. Echo: mild mitral regurgitation. {note}"),
                 doc("Cost estimate", "HOSPITAL_ESTIMATE", f"Malabar Heart Centre, Kozhikode\nEstimate No. MHC/E/310, issued on {d(-12)}\n"
                     f"Patient: Meera Pillai. Valve replacement package Rs 3,20,000. Estimate valid until {d(40)}.")], "SELF")


def test_treatment_not_indicated_is_a_contradiction():
    out = run(_cardiac("Surgical management is not advised at this stage; continue medication."))
    assert out.decision == "FLAG_FOR_REVIEW" and "TREATMENT_NOT_INDICATED" in out.triggers[0]


def test_v3_amount_finding_built_on_a_year_is_refuted():
    """Frozen V3 reads '2026' in 'valid until DD/MM/2026' as the documented total and flags the request as 157.9x it."""
    out = run(_cardiac("Valve replacement advised."))
    assert out.v3_decision == "FLAG_FOR_REVIEW" and any("year of a date" in r for r in out.refuted_v3_findings)
    assert out.decision == "APPROVED"


def test_negation_of_a_different_treatment_is_not_a_contradiction():
    out = run(_cardiac("Chemotherapy is not indicated. Valve replacement advised."))
    assert not [f for f in out.cross_document_findings if f["code"] == "TREATMENT_NOT_INDICATED"]


def test_outstanding_amount_conflict_from_the_same_issuer():
    letter = doc("Dues letter", "OTHER", f"Indus Valley Hospital, Pune\nDate: {d(-4)}\nPatient: Farhan Qureshi. "
                                         "Outstanding dues: Rs 62,000.")
    out = run(medical_bill(extra=[letter]))
    assert out.decision == "FLAG_FOR_REVIEW"
    assert "OUTSTANDING_AMOUNT_CONFLICT" in out.triggers[0] or out.triggers == ["V3_CONTRADICTION"]


def test_place_of_death_contradiction_still_depends_on_gemini():
    """A contradiction with no date, identifier, age, sex, treatment or amount difference is NOT detected by the
    deterministic checks; it is listed as Gemini-dependent and only Gemini (or a reviewer) can raise it."""
    c = _memorial(-4)
    c["documents"][1]["content"] = c["documents"][1]["content"] + " Place of death: residence, Srirangam."
    assert not run(c).cross_document_findings
    assert any("place" in item.lower() for item in GEMINI_DEPENDENT)


# ------------------------------------------------------------------ 3. fabricated institutions (DA-06)
FABRICATED_NGO = case(
    "Water tanker for Saraswati Gram Seva Samiti", "COMMUNITY",
    "Saraswati Gram Seva Samiti supplies drinking water to four hamlets near Jhalawar. We are raising Rs 4,80,000 for a "
    "tanker. Our registration, committee resolution and the dealer's quotation are attached.", 480000,
    "Saraswati Gram Seva Samiti",
    [doc("Registration certificate", "REGISTRATION_EXTRACT", f"Office of the Registrar of Societies, Kota\nRegistration No. "
         f"KOTA/S/4471, dated {d(-700)}\nName of society: Saraswati Gram Seva Samiti. Objects: drinking water and sanitation."),
     doc("Committee resolution", "COMMITTEE_RESOLUTION", f"Saraswati Gram Seva Samiti\nMeeting held on {d(-21)}\nResolved to buy "
         "one 5,000-litre water tanker from Hadoti Tankers, Kota, at a cost not exceeding Rs 4,80,000. Secretary authorised."),
     doc("Dealer quotation", "SUPPLIER_QUOTE", f"Hadoti Tankers, Kota\nQuotation No. HT/Q/118, Date: {d(-18)}\nTo: Saraswati Gram "
         "Seva Samiti. Tanker body Rs 3,10,000; chassis mounting Rs 1,20,000; pump and fittings Rs 50,000. Total: Rs 4,80,000. "
         "Quotation valid for 60 days.")], "ORGANISATION")


def test_consistent_documents_never_mean_authentic_or_active():
    out = run(FABRICATED_NGO)
    assert out.decision in ("APPROVED", "NEEDS_MORE_INFORMATION")
    assert out.workflow_state != "VERIFIED_ACTIVE" and out.authenticity == "UNCONFIRMED"
    if out.decision == "APPROVED":
        assert out.workflow_state == "ELIGIBLE_PENDING_CONFIRMATION"
        assert set(out.required_confirmations) == {"BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION"}
        assert "not proof of authenticity" in out.reasons[0]


def _confirm(record, check, source=ContactSource.OFFICIAL_REGISTRY, outcome=ConfirmationOutcome.CONFIRMED):
    return record_confirmation(record, ConfirmationRecord(check=check, outcome=outcome, contact_source=source,
                                                          verifier_id="ops-1"))


ALL_CHECKS = [ConfirmationCheck.BENEFICIARY, ConfirmationCheck.PAYMENT_DESTINATION, ConfirmationCheck.INSTITUTION]


def test_activation_requires_all_three_independent_confirmations():
    record = start_record("APPROVED", "COMMUNITY", "ORGANISATION")
    assert not activation_status(record)["activation_allowed"] and not record.disbursement_allowed
    for check in ALL_CHECKS:                                   # only campaign-supplied contacts
        record = _confirm(record, check, ContactSource.CAMPAIGN_SUPPLIED)
    assert not activation_status(record)["activation_allowed"]
    record = start_record("APPROVED", "COMMUNITY", "ORGANISATION")
    for check in ALL_CHECKS[:2]:                               # institution unconfirmed
        record = _confirm(record, check)
    status = activation_status(record)
    assert not status["activation_allowed"] and status["pending_checks"] == ["INSTITUTION"]
    record = _confirm(record, ConfirmationCheck.INSTITUTION, outcome=ConfirmationOutcome.UNREACHABLE)
    assert not activation_status(record)["activation_allowed"]
    record = _confirm(record, ConfirmationCheck.INSTITUTION)   # positive control: the path exists
    status = activation_status(record)
    assert status["activation_allowed"] and status["authenticity"] == "CONFIRMED_BY_INDEPENDENT_SOURCES"


def test_institution_contradiction_sends_to_review_and_reviewers_cannot_activate():
    record = _confirm(start_record("APPROVED", "COMMUNITY", "ORGANISATION"), ConfirmationCheck.INSTITUTION,
                      outcome=ConfirmationOutcome.CONTRADICTED)
    assert record.state == WorkflowState.FLAG_FOR_REVIEW
    with pytest.raises(IllegalTransition):
        reviewer_resolution(record, WorkflowState.VERIFIED_ACTIVE, "reviewer-1", "looks fine")


# ------------------------------------------------------------------ 4. dates (DA-04)
def _kinds(text, title="Surgeon's letter", doc_type="CLINICAL_NOTE"):
    return {x.raw: (x.kind, x.status) for x in assess_text(title, text, doc_type, REF)}


def test_scheduled_surgery_is_not_a_future_issued_document():
    text = (f"Date of surgery: {d(20)}\nSahyadri Children's Hospital, Pune\nDate: {d(-3)}\nPlan: tendon release. "
            f"Surgery date: {d(20)}. Admission on {d(19)}. Proposed date of surgery: {d(20)}. Next review on {d(45)}.")
    kinds = _kinds(text)
    assert kinds[d(-3)] == ("issue", "VALID")
    assert all(status != "FUTURE" for raw, (_, status) in kinds.items())


def test_genuinely_future_dated_records_are_detected():
    assert _kinds(f"City Hospital\nBill date: {d(15)}\nTotal Rs 9,000.", "Final bill", "FINAL_BILL")[d(15)] == ("issue", "FUTURE")
    summary = _kinds(f"City Hospital\nDischarge Summary, dated {d(-1)}\nDate of discharge: {d(12)}.", "Discharge summary",
                     "DISCHARGE_SUMMARY")
    assert summary[d(12)] == ("completed", "FUTURE")


def test_expiry_explicit_relative_and_staleness_are_separate():
    assert _kinds(f"X College\nDate: {d(-40)}\nValid until {d(-2)}.", "Fee notice", "FEE_STATEMENT")[d(-2)] == ("validity", "EXPIRED")
    relative = assess_text("Quotation", f"Y Traders\nDate: {d(-90)}\nValid for 30 days.", "SUPPLIER_QUOTE", REF)
    assert any(x.kind == "relative_validity" and x.status == "EXPIRED" for x in relative)
    assert _kinds(f"Registrar of Societies\nRegistration No. A/1, dated {d(-1100)}", "Registration certificate",
                  "REGISTRATION_EXTRACT")[d(-1100)] == ("issue", "VALID")           # not time-sensitive
    assert _kinds(f"Tehsil Office\nIncome certificate issued on {d(-500)}", "Income certificate",
                  "INCOME_CERTIFICATE")[d(-500)] == ("issue", "EXPIRED")             # time-sensitive and stale


def test_v3_future_date_finding_on_a_scheduled_surgery_is_refuted():
    c = case("Clubfoot correction for Aarav Joshi", "MEDICAL",
             f"Our son Aarav Joshi needs clubfoot correction surgery at Sahyadri Children's Hospital, planned for {d(20, 'long')}. "
             "The estimate is Rs 85,000.", 85000, "Aarav Joshi",
             [doc("Surgeon's letter", "CLINICAL_NOTE", f"Sahyadri Children's Hospital, Pune\nDate: {d(-3)}\nPatient: Aarav Joshi, "
                  f"MRN SCH-7710.\nDiagnosis: congenital talipes equinovarus. Proposed date of surgery: {d(20)}."),
              doc("Cost estimate", "HOSPITAL_ESTIMATE", f"Sahyadri Children's Hospital, Pune\nEstimate No. SCH/E/55, issued on "
                  f"{d(-3)}\nPatient: Aarav Joshi, MRN SCH-7710. Clubfoot correction package Rs 85,000. Estimate valid until {d(50)}.")],
             "FAMILY")
    out = run(c)
    if out.v3_decision == "FLAG_FOR_REVIEW":
        assert out.refuted_v3_findings, "V3 flagged; its future-date finding must be re-checked"
    assert out.decision != "FLAG_FOR_REVIEW" and not [t for t in out.triggers if "FUTURE" in t]


def test_a_future_dated_bill_is_still_flagged():
    future = medical_bill()
    future["documents"][1]["content"] = future["documents"][1]["content"].replace(f"Bill date: {d(-5)}", f"Bill date: {d(25)}")
    out = run(future)
    assert out.decision == "FLAG_FOR_REVIEW"


# ------------------------------------------------------------------ 5. Gemini warnings
def test_gemini_warnings_are_separated_by_evidence():
    c = education([BONAFIDE, QUOTE])
    grounded = {"status": "OK", "decision": "FLAG_FOR_REVIEW", "red_flag_texts": [], "missing_requirements": [],
                "concerns": [{"category": "CONTRADICTION", "description": "The quotation includes tuition that the story omits.",
                              "document_title": "Supplier quotation", "evidence_quote": "tuition fee for the year Rs 21,500"}]}
    out = run(c, grounded)
    assert out.decision == "FLAG_FOR_REVIEW" and out.review_basis == "DOCUMENT_SUPPORTED_MODEL_FINDING"
    out = run(c, FLAG_UNGROUNDED)
    assert out.decision == "FLAG_FOR_REVIEW" and out.review_basis == "UNVERIFIED_MODEL_SUSPICION"
    assert run(c, REJECT_UNGROUNDED).decision == "FLAG_FOR_REVIEW"                   # Gemini never rejects
    out = run(c, APPROVE_UNGROUNDED)
    assert out.decision == "NEEDS_MORE_INFORMATION" and out.unverified_concerns          # suspicion, not finding
    assert run(c, FAILED).decision == "VERIFICATION_ERROR"                              # fail closed


# ------------------------------------------------------------------ 6. no missing evidence can lead to approval
def _rendered_da_cases():
    path = ROOT / "evaluation/runs/date_aware_dev_eval_live/rendered_cases.jsonl"
    return [json.loads(line)["input"] for line in path.read_text().splitlines() if line.strip()]


ALL_CASES = [education([BONAFIDE, QUOTE]), education([BONAFIDE]), medical_bill(), _memorial(-150), _memorial(-5),
             _cardiac("Valve replacement advised."), FABRICATED_NGO] + _rendered_da_cases()


@pytest.mark.parametrize("index", range(len(ALL_CASES)))
def test_approval_only_with_complete_unresolved_free_evidence(index):
    """Exhaustive over document subsets x Gemini outputs: APPROVED implies every gate passed."""
    base = ALL_CASES[index]
    docs = base["documents"]
    for size in range(len(docs) + 1):
        for subset in itertools.combinations(range(len(docs)), size):
            c = dict(base, documents=[docs[i] for i in subset])
            for gemini in GEMINI_OUTPUTS:
                out = run(c, gemini)
                assert out.workflow_state != "VERIFIED_ACTIVE"
                assert out.decision != "REJECTED" or out.v3_effective_decision == "REJECTED"
                if out.decision == "APPROVED":
                    assert gemini is APPROVE
                    assert out.financial_evidence["status"] == "SUPPORTED"
                    assert out.v3_effective_decision == "APPROVED"
                    assert not out.open_items and not out.cross_document_findings and not out.unverified_concerns
                    assert out.workflow_state == "ELIGIBLE_PENDING_CONFIRMATION" and out.authenticity == "UNCONFIRMED"
                    assert set(out.required_confirmations) == {"BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION"}


# ------------------------------------------------------------------ 7. labelled scenarios (Gemini approves cleanly)
@pytest.mark.parametrize("name,c,expected", [
    ("legitimate, complete", education([BONAFIDE, QUOTE]), {"APPROVED"}),
    ("legitimate, complete medical", medical_bill(), {"APPROVED"}),
    ("incomplete: no cost document", education([BONAFIDE]), {"NEEDS_MORE_INFORMATION"}),
    ("incomplete: no documents", education([]), {"NEEDS_MORE_INFORMATION"}),
    ("borderline: goal 4% above the quotation", education([BONAFIDE, QUOTE], goal=46800), {"APPROVED"}),
    ("borderline: death dates 1 day apart", _memorial(-5), {"APPROVED", "NEEDS_MORE_INFORMATION"}),
    ("fraud: conflicting death dates", _memorial(-150), {"FLAG_FOR_REVIEW"}),
    ("fraud: discharge date contradicted", medical_bill(story_discharge=-60), {"FLAG_FOR_REVIEW"}),
    ("fraud: surgery not advised", _cardiac("Surgical management is not advised; continue medication."), {"FLAG_FOR_REVIEW"}),
    ("fraud: fabricated but consistent (confirmation is the control)", FABRICATED_NGO, {"APPROVED", "NEEDS_MORE_INFORMATION"}),
])
def test_labelled_scenarios(name, c, expected):
    assert run(c).decision in expected, name


# ------------------------------------------------------------------ 8. DA regressions (development cases, in-sample)
@pytest.mark.parametrize("case_id,gemini,expected", [
    ("DA-07", APPROVE, "NEEDS_MORE_INFORMATION"), ("DA-05", APPROVE, "FLAG_FOR_REVIEW"), ("DA-05", FAILED, "FLAG_FOR_REVIEW"),
    ("DA-04", APPROVE, "NEEDS_MORE_INFORMATION"), ("DA-02", APPROVE, "NEEDS_MORE_INFORMATION"),
    ("DA-03", APPROVE, "FLAG_FOR_REVIEW"), ("DA-08", APPROVE, "FLAG_FOR_REVIEW"), ("DA-01", APPROVE, "APPROVED"),
    ("DA-06", APPROVE, "APPROVED"),
])
def test_da_cases(case_id, gemini, expected):
    rendered = [json.loads(l) for l in (ROOT / "evaluation/runs/date_aware_dev_eval_live/rendered_cases.jsonl").read_text().splitlines()]
    c = next(r["input"] for r in rendered if r["case_id"] == case_id)
    out = run(c, gemini)
    assert out.decision == expected
    if case_id == "DA-04":
        assert out.refuted_v3_findings and out.triggers != ["V3_CONTRADICTION"]
    if case_id == "DA-06":
        assert out.workflow_state == "ELIGIBLE_PENDING_CONFIRMATION" and out.authenticity == "UNCONFIRMED"


# ------------------------------------------------------------------ 9. integrity
def test_frozen_manifests_still_verify():
    import sys
    sys.path.insert(0, str(ROOT / "evaluation"))
    from freeze_hybrid_v2 import verify as verify_hybrid_v2
    from verify_candidate_v3_freeze import verify as verify_v3
    assert verify_hybrid_v2()["valid"] and verify_v3()["valid"]


def test_production_code_does_not_import_the_development_package():
    offenders = [p for p in (ROOT / "app").rglob("*.py")
                 if "development_" not in str(p.relative_to(ROOT)) and "development_hybrid_v3" in p.read_text()]
    assert not offenders
