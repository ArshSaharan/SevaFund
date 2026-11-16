"""Author the fixed, synthetic v2 development corpus (multi-document dossiers).

Design goals (see docs/development_verifier_v2.md):
  * 15 scenario families (5 medical, 5 education, 5 community); each family has
    its own document sources, layouts, and field vocabulary.
  * Families are assigned wholesale to a `tune` split (9 families) or a
    `validation` split (6 families), so no family or document source crosses
    the split.
  * Every family yields 3 legitimate, 3 fraudulent, and 2 borderline cases.
  * Fraud includes cases that are NOT detectable from the dossier alone
    (consistently fabricated paperwork) and cases whose correct offline outcome
    is an information request (thin evidence).  These cap achievable recall on
    purpose; labels are never adjusted to suit a verifier.

Everything is invented.  No real person, patient, student, or organisation
record is represented.  The file is deterministic: no randomness is used.
"""
import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).with_name("development_scenarios_v2.jsonl")
REFERENCE_DATE = date(2026, 10, 5)

FIRST = ["Rakesh", "Sunita", "Imran", "Lakshmi", "Gurpreet", "Ananya", "Joseph", "Fatima", "Dinesh", "Meenal",
         "Tsering", "Kavitha", "Arif", "Pallavi", "Santosh", "Rubina", "Harish", "Nandini", "Vikram", "Shabnam"]
MIDDLE = ["Kumar", "Devi", "Ahmed", "Bai", "Singh", "Rani", "Mathew", "Begum", "Lal", "Prasad"]
LAST = ["Sharma", "Deshmukh", "Khan", "Iyer", "Sandhu", "Mukherjee", "Thomas", "Ansari", "Yadav", "Joshi", "Bhutia",
        "Reddy", "Shaikh", "Kulkarni", "Mahato", "Qureshi", "Gowda", "Pillai", "Rathore", "Mirza", "Baruah",
        "Chaudhary", "Naik"]
MONEY_KEYS = {"total", "paid", "balance", "covered", "goal", "story_total", "i1", "i2", "i3", "i4", "old_total"}


class Money:
    """Rupee amount whose textual style is chosen by the template (`{x:m1}`)."""

    def __init__(self, value, shift=0):
        self.value, self.shift = int(round(value)), shift

    @staticmethod
    def indian(value):
        digits = str(value)
        if len(digits) <= 3:
            return digits
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        return ",".join(groups) + "," + tail

    def __format__(self, spec):
        style = int(spec[1:]) if spec else 0
        if style != 5:
            style = (style + self.shift) % 5
        grouped = self.indian(self.value)
        if style == 0:
            return f"₹{grouped}"
        if style == 1:
            return f"Rs. {grouped}/-"
        if style == 2:
            return f"INR {grouped}.00"
        if style == 3:
            return f"Rs {self.value}"
        if style == 4:
            if self.value >= 100000 and self.value % 1000 == 0:
                return f"₹{self.value / 100000:.2f} lakh"
            return f"Rs.{grouped}"
        return grouped


class Day:
    STYLES = ["%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%d.%m.%Y", "%Y-%m-%d"]

    def __init__(self, value, shift=0):
        self.value, self.shift = value, shift

    def __format__(self, spec):
        style = (int(spec[1:]) if spec else 0)
        return self.value.strftime(self.STYLES[(style + self.shift) % len(self.STYLES)])


def render(template, view):
    shift = view.get("shift", 0)
    values = {}
    for key, value in view.items():
        if key in MONEY_KEYS:
            values[key] = Money(value, shift)
        elif key.startswith("d_"):
            values[key] = Day(value, shift)
        else:
            values[key] = value
    return template.format(**values)


# --------------------------------------------------------------------------
# Scenario families.  `split` is assigned per family, never per case.
# --------------------------------------------------------------------------
FAMILIES = [
    # ============================ MEDICAL ================================
    dict(
        key="renal_transplant", category="MEDICAL", split="tune",
        source="transplant_unit_estimate_and_nephrology_summary", base_total=780000,
        inst="Sahyadri Institute of Renal Sciences", inst_short="Sahyadri Inst. of Renal Sciences",
        inst_alt="Lotus Kidney Care Hospital", city="Pune", state="Maharashtra", staff="Dr. Vivek Kulkarni",
        service="living-donor kidney transplant", service_alt="laparoscopic gall bladder removal",
        pid_fmt="SIRS/2026/{n:05d}",
        title="Kidney transplant for {person_first}",
        story=("{person}, {age}, has been on dialysis three times a week since last year after both kidneys failed. "
               "Doctors at {inst}, {city} have advised a {service}; {person_first}'s mother is the donor and the "
               "work-up is complete. The hospital has given us a written estimate of {story_total:m0}. We are raising "
               "{goal:m0} towards the transplant admission.{story_extra}"),
        docs=[
            ("HOSPITAL_ESTIMATE", "Transplant cost estimate", """{inst}
Department of Nephrology & Transplant, {city}

ESTIMATE OF EXPENSES                                   Ref: EST/{n}
Date: {d_issue:d0}

Patient Name : {person}
UHID         : {pid}
Age / Sex    : {age} Y
Consultant   : {staff}
Procedure    : {service} (recipient and donor)
Expected stay: 12 days

Particulars
  Pre-transplant work-up ............ {i1:m5}
  Surgery, OT and anaesthesia ....... {i2:m5}
  ICU and ward stay ................. {i3:m5}
  Immunosuppressant induction ....... {i4:m5}
Total estimated cost : {total:m1}

{status_line}
{pay_line}
This estimate is approximate and may vary with the clinical course."""),
            ("CLINICAL_SUMMARY", "Nephrology case summary", """{inst} - Nephrology OPD
Case summary dated {d_start:d2}

Name: {person}        Hospital No: {pid}
Diagnosis: Chronic kidney disease stage 5 on maintenance haemodialysis
History: On thrice-weekly dialysis. Donor (mother) evaluated and found fit.
Advice: {service}. Admission planned on {d_end:d2}.
Treating nephrologist: {staff}"""),
        ],
        status=dict(
            open="Payment status: no deposit received as on date.",
            settled=("Payment status: the entire estimate amount of {total:m1} has been sanctioned under the State "
                     "Health Assurance Scheme (cashless); nothing is payable by the patient."),
            partial="Payment status: deposit of {paid:m1} received; balance payable {balance:m1}.",
            provisional=("PROVISIONAL - donor cross-match report awaited; transplant committee approval is pending "
                         "and this estimate is not final."),
        ),
        pay=dict(open="Payments are accepted only at the hospital billing counter or by NEFT to {inst}."),
        fraud=["identity_mismatch", "already_settled", "amount_inflation"],
        legit_special="partial_paid", border=["no_documents", "provisional"],
    ),
    dict(
        key="neonatal_icu", category="MEDICAL", split="tune",
        source="nicu_interim_bill_and_admission_record", base_total=412000,
        inst="Rainbow Cradle Children's Hospital", inst_short="Rainbow Cradle Hospital",
        inst_alt="Sunrise Mother & Child Clinic", city="Hyderabad", state="Telangana", staff="Dr. Farah Siddiqui",
        service="NICU care for a preterm baby with respiratory distress",
        service_alt="adult cardiac bypass surgery", pid_fmt="NICU/26/{n}",
        title="NICU care for baby {person_first}",
        story=("Our baby {person} was born at 30 weeks and has been in the neonatal ICU at {inst}, {city} since "
               "birth. The doctors expect at least three more weeks of ventilator and incubator care. The interim "
               "bill already stands at {story_total:m0}, and we are requesting {goal:m0}.{story_extra}"),
        docs=[
            ("INTERIM_BILL", "NICU interim bill", """{inst}, {city}
INTERIM IN-PATIENT BILL

Bill No.            IB-{n}                Bill Date   {d_issue:d1}
Patient             {person} (preterm neonate)
IP No               {pid}
Parent/Guardian     {guardian}
Treating Doctor     {staff}

Description                               Amount (Rs.)
NICU bed charges (level III)              {i1:m5}
Ventilator and CPAP support               {i2:m5}
Medicines, surfactant and consumables     {i3:m5}
Investigations                            {i4:m5}
----------------------------------------------------
Interim bill amount                       {total:m5}
{status_line}

{pay_line}"""),
            ("ADMISSION_RECORD", "NICU admission record", """{inst}
Neonatal Intensive Care Unit - Admission Record

Baby's name: {person}
IP No: {pid}
Date of Admission: {d_start:d1}
Mother/Father: {guardian}
Gestational age at birth: 30 weeks, birth weight 1.24 kg
Provisional diagnosis: Prematurity with respiratory distress syndrome
Plan: {service}
Admitting neonatologist: {staff}"""),
        ],
        status=dict(
            open="Amount received so far                    0",
            settled="Amount received so far                    {total:m5}\nBalance due                               NIL (bill settled in full)",
            partial="Amount received so far                    {paid:m5}\nBalance due                               {balance:m5}",
            provisional="",
        ),
        pay=dict(
            open="Payment mode: cash/card at the billing desk; cheques in favour of {inst}.",
            diverted=("Kindly remit the dues to A/c holder: {other_person}, Savings A/c 50100{n}77, "
                      "IFSC HDFC0001{n}, or UPI {upi}."),
        ),
        date_break=(1, "d_start", "d_issue", 6),  # admission recorded after the bill that covers it
        fraud=["id_mismatch", "date_impossible", "payment_diversion"],
        legit_special="high_cost", border=["modest_excess", "ambiguous_identity"],
    ),
    dict(
        key="spinal_surgery", category="MEDICAL", split="tune",
        source="surgeon_estimate_letter_and_imaging_report", base_total=365000,
        inst="Narmada Spine & Joint Hospital", inst_short="Narmada Spine and Joint Hosp.",
        inst_alt="Kaveri Multispeciality Hospital", city="Indore", state="Madhya Pradesh",
        staff="Dr. Sameer Bhargava", service="L4-L5 spinal fusion surgery (TLIF)",
        service_alt="total knee replacement of the right knee", pid_fmt="NSJ-{n}",
        inst_doc=0, svc_doc=0,
        title="Spine surgery for {person_first}",
        story=("{person} is a {age}-year-old daily-wage mason who can no longer stand for more than a few minutes "
               "because of a slipped disc pressing on the nerves. After an MRI, the surgeon at {inst} in {city} has "
               "recommended {service}. The surgeon's letter puts the cost at {story_total:m0}; we need {goal:m0}."
               "{story_extra}"),
        docs=[
            ("ESTIMATE_LETTER", "Surgeon's estimate letter", """{inst}
{city}

{d_issue:d2}

TO WHOMSOEVER IT MAY CONCERN

This is to certify that {person}, aged {age} years (registration number {pid}), is under my care for lumbar canal
stenosis with disc prolapse. The patient has been advised {service}. The approximate cost of the operation,
including implants, hospital stay of five days and physiotherapy, will be {total:m0}.
{status_line}
This letter is issued at the request of the patient's family for the purpose of arranging financial assistance.

{staff}
Consultant Spine Surgeon"""),
            ("MRI_REPORT", "MRI lumbar spine report", """Clarity Diagnostics & Imaging Centre, {city}
MRI LUMBO-SACRAL SPINE

Patient: {person}     Age: {age}     Ref. by: {staff}
Scan date: {d_start:d3}     Report ID: MR{n}

Findings: Diffuse disc bulge with large central extrusion at L4-L5 causing severe canal stenosis and bilateral
nerve root compression. Mild degenerative changes at L5-S1.
Impression: L4-L5 disc extrusion with severe canal stenosis. Surgical opinion advised."""),
        ],
        revision_doc=("ESTIMATE_LETTER", "Earlier estimate (superseded)", """{inst}
{city}

{d_start:d2}

Estimate for {person} (registration number {pid}): the approximate cost of {service} with standard implants will be
{old_total:m0}. This estimate will be revised if navigation-guided implants are required.

{staff}"""),
        status=dict(
            open="",
            provisional=("This is a tentative figure only: fitness for anaesthesia has not been assessed and the "
                         "operation has not yet been scheduled or confirmed."),
        ),
        pay=dict(open=""),
        fraud=["service_mismatch", "institution_mismatch", "consistent_fabricated"],
        legit_special="estimate_revision", border=["provisional", "no_documents"],
    ),
    dict(
        key="leukemia_chemo", category="MEDICAL", split="validation", age_base=9,
        source="oncology_protocol_cost_sheet_and_discharge_summary", base_total=640000,
        inst="Malabar Cancer Centre and Research Institute", inst_short="Malabar Cancer Centre",
        inst_alt="Periyar District Co-operative Hospital", city="Kozhikode", state="Kerala",
        staff="Dr. Anjali Menon", service="induction chemotherapy for acute lymphoblastic leukaemia",
        service_alt="hernia repair", pid_fmt="MR{n}26",
        title="Help {person_first} fight blood cancer",
        story=("{person} ({age}) was diagnosed with blood cancer two months ago. The oncology team at {inst}, "
               "{city} has started a chemotherapy protocol that will run for about six months. The centre's cost "
               "sheet comes to {story_total:m0}. We are appealing for {goal:m0} for the remaining cycles."
               "{story_extra}"),
        docs=[
            ("PROTOCOL_COST_SHEET", "Chemotherapy protocol cost sheet", """[Page 1]
{inst}
Paediatric and Adult Haemato-Oncology Division

TREATMENT COST SHEET        Sheet no. HO/{n}        Issued on {d_issue:d3}
Pt. Name: {person}          MR No.: {pid}
Dx: Acute lymphoblastic leukaemia (B-cell)
Planned treatment: {service}, followed by consolidation and maintenance
Physician in charge: {staff}

Phase              Cycles    Amount in Rs.
Induction            1       {i1:m5}
Consolidation        3       {i2:m5}
Maintenance          6       {i3:m5}
Supportive care      -       {i4:m5}
[Page 2]
Gross protocol cost: {total:m2}
{status_line}
Costs exclude unforeseen ICU admissions. Issued for the purpose of seeking financial aid."""),
            ("DISCHARGE_SUMMARY", "Discharge summary (first admission)", """{inst}
DISCHARGE SUMMARY

{person}, a {age}-year-old, was admitted on {d_start:d4} with fever, fatigue and bruising. Bone marrow examination
confirmed acute lymphoblastic leukaemia. The patient (MR No. {pid}) received the first block of chemotherapy and
tolerated it well, and was discharged on {d_issue:d4} in stable condition with advice to return for the next cycle.
Signed: {staff}, Consultant Haemato-oncologist"""),
        ],
        thin_doc=("OTHER", "Cost note", """Estimate

Chemotherapy for {person} will cost about {total:m0} in all. Kindly help the family.

(typed note - no letterhead, reference number, date or signature)"""),
        status=dict(
            open="Assistance received from schemes/insurance: none recorded.",
            settled=("The full protocol cost is being borne by the Chief Minister's Distress Relief Fund (sanction "
                     "order CMDRF/{n}); no amount is due from the family."),
            partial="Assistance received from schemes/insurance: {paid:m2}. Net amount to be arranged by family: {balance:m2}.",
            provisional="",
        ),
        pay=dict(open=""),
        dates=dict(d_start=-34, d_issue=-14, d_end=25, d_due=30),
        fraud=["already_settled+identity_mismatch", "amount_inflation", "thin_evidence"],
        legit_special="partial_goal", border=["ambiguous_identity", "modest_excess"],
    ),
    dict(
        key="road_accident_trauma", category="MEDICAL", split="validation",
        source="trauma_final_bill_admission_note_and_police_memo", base_total=298000,
        inst="Trinity Trauma & Orthopaedic Hospital", inst_short="Trinity Trauma and Ortho Hospital",
        inst_alt="Wardha Road Eye Institute", city="Nagpur", state="Maharashtra", staff="Dr. Rohit Deshpande",
        service="open reduction and internal fixation of a fractured femur",
        service_alt="cataract surgery of the left eye", pid_fmt="TT/IPD/{n}", svc_doc=0,
        title="{person_first} needs help after a highway accident",
        story=("{person}, {age}, was hit by a truck while cycling home from work and was rushed to {inst}, {city}. "
               "Surgeons had to operate the same night to fix the thigh bone with a rod. The family has no "
               "insurance and the hospital's final bill is {story_total:m0}. We are trying to raise {goal:m0} to "
               "clear the bill and bring {person_first} home.{story_extra}"),
        docs=[
            ("FINAL_BILL", "Final hospital bill", """{inst}
{city}
FINAL BILL CUM RECEIPT SUMMARY

Invoice #: FB{n}                       Dated: {d_issue:d5}
Name of patient: {person}
IPD Regn. No.: {pid}
Operating surgeon: {staff}
Surgery performed: {service}

Gross bill amount ........................ {total:m3}
Less: paid by TPA / insurer .............. {covered:m3}
Less: deposits received .................. {paid:m3}
Net payable by patient ................... {balance:m3}
{status_line}"""),
            ("ADMISSION_NOTE", "Emergency admission and discharge note", """{inst} - Emergency & Trauma
Name of patient: {person}    IPD Regn. No.: {pid}
DOA: {d_start:d5}    DOD: {d_end:d5}
Brought by: bystanders, following a road traffic accident
Injury: closed fracture of the shaft of the right femur
Management: {service} under spinal anaesthesia on the day of admission
Condition at discharge: stable, non-weight-bearing for six weeks
Doctor: {staff}"""),
            ("POLICE_MEMO", "Accident intimation memo", """Office of the Station House Officer, Sitabuldi Police Station, {city}
Accident intimation memo no. {n}/2026

It is recorded that on {d_start:d2} a cyclist, {person}, was struck by a goods vehicle on the ring road and was
shifted to hospital by passers-by. A case has been registered and investigation is in progress. This memo is issued
to the injured person's family on request."""),
        ],
        status=dict(
            open="Bill status: UNPAID.",
            settled="Bill status: SETTLED - no dues pending.",
            partial="Bill status: part paid.",
            provisional=("DRAFT bill for information only - the patient is still admitted; final charges will be "
                         "known at discharge and this draft is not valid for claims."),
        ),
        pay=dict(open=""),
        dates=dict(d_start=-30, d_end=-12, d_issue=-12, d_due=20),
        date_break=(0, "d_issue", "d_start", -40),  # final bill dated well before the admission it bills
        keep_when_missing=[2], provisional_keep=[0, 2],
        fraud=["date_impossible", "id_mismatch", "service_mismatch"],
        legit_special="missing_required", border=["provisional", "no_documents"],
    ),
    # ============================ EDUCATION ==============================
    dict(
        key="engineering_tuition", category="EDUCATION", split="tune",
        source="college_fee_demand_notice_and_bonafide_certificate", base_total=118000,
        inst="Vishwakarma Government College of Engineering", inst_short="Vishwakarma Govt. College of Engg.",
        inst_alt="Deccan Institute of Hotel Management", city="Aurangabad", state="Maharashtra",
        staff="Dr. S. R. Patwardhan", service="B.Tech (Civil Engineering), second year",
        service_alt="Diploma in Fashion Design, first year", pid_fmt="22CE{n}",
        title="Second-year engineering fees for {person_first}",
        story=("{person} is the first in the family to reach college and is studying civil engineering at {inst}, "
               "{city}. {person_first}'s father lost his job at a textile mill this year and the family cannot pay "
               "the second-year fees. The college fee notice is for {story_total:m0} and we are raising {goal:m0}."
               "{story_extra}"),
        docs=[
            ("FEE_DEMAND_NOTICE", "Fee demand notice", """{inst}, {city}
ACCOUNTS SECTION - FEE DEMAND NOTICE              No. FDN/{n}        Date: {d_issue:d0}

Name of Student : {person}
Roll No.        : {pid}
Course          : {service}
Academic Year   : 2026-27

Tuition fee          {i1:m5}
Development fee      {i2:m5}
Examination fee      {i3:m5}
Hostel and mess      {i4:m5}
Total fee payable : {total:m1}
Last date for payment : {d_due:d0}
{status_line}
{pay_line}
Admission is liable to be cancelled if the fee is not paid by the last date."""),
            ("BONAFIDE_CERTIFICATE", "Bonafide certificate", """{inst}
{city}
Ref: BC/{n}                                              Date: {d_start:d0}

BONAFIDE CERTIFICATE

This is to certify that {person}, Roll No. {pid}, son/daughter of {guardian}, is a bonafide student of this
college studying in {service} during the academic year 2026-27.

{staff}
Principal"""),
        ],
        status=dict(
            open="Scholarship/fee waiver: none.",
            settled=("Fee status: FULL FEE WAIVER granted under the State Post-Matric Scholarship; amount payable by "
                     "the student: Rs. 0."),
            partial="Scholarship adjusted: {paid:m1}; balance payable by student: {balance:m1}.",
            provisional=("PROVISIONAL NOTICE - fee slab subject to verification of the income certificate; the "
                         "final demand has not yet been raised."),
            ineligible=("Note: as per academic section records the above roll number stands cancelled (name struck "
                        "off the rolls with effect from {d_start:d0}) for non-attendance."),
        ),
        pay=dict(open="Fees are to be paid only through the college online portal or by DD in favour of the Principal, {inst}."),
        solicit=(" Since the college portal is slow, donors can also send the amount straight to my cousin's number "
                 "on GPay and he will deposit it for us."),
        fraud=["already_settled", "payment_diversion", "ineligible"],
        legit_special="partial_paid", border=["modest_excess", "provisional"],
    ),
    dict(
        key="nursing_diploma", category="EDUCATION", split="tune",
        source="nursing_school_fee_structure_and_admission_letter", base_total=96000,
        inst="St. Theresa School of Nursing", inst_short="St Theresa Nursing School",
        inst_alt="Mar Baselios College of Paramedical Studies", city="Kottayam", state="Kerala",
        staff="Sr. Mary Francis", service="General Nursing and Midwifery (GNM) diploma, first year",
        service_alt="B.Sc. Computer Science, first year", pid_fmt="GNM/2026/{n}", relative_mismatch=True,
        title="Nursing course fees for {person_first}",
        story=("{person} has secured admission to the nursing diploma at {inst}, {city}. {person_first}'s mother "
               "works as a home nurse and cannot manage the first-year fee and hostel deposit together. As per the "
               "school's fee structure the first-year amount is {story_total:m0}. This appeal is for {goal:m0}."
               "{story_extra}"),
        docs=[
            ("FEE_STRUCTURE", "First-year fee structure", """{inst}
{city}
FEE STRUCTURE FOR THE ACADEMIC YEAR 2026-27 ({service})
Issued to: {person}, Application No. {pid}, on {d_issue:d2}

  Sl.  Head of account                 Rupees
  1    Tuition                         {i1:m5}
  2    Uniform, books and clinical kit {i2:m5}
  3    Hostel deposit and rent         {i3:m5}
  4    University registration         {i4:m5}
       Total payable for first year    {total:m5}
{status_line}
Fees once paid are not refundable. {pay_line}"""),
            ("ADMISSION_LETTER", "Admission letter", """{inst}, {city}
Date: {d_start:d2}

Dear {person},

We are pleased to inform you that you have been selected for admission to the {service} for the batch commencing
in 2026. Your application number is {pid}. You are required to report to the school office with original
certificates and remit the first-year fee on or before {d_due:d2}.

{staff}
Principal"""),
        ],
        status=dict(
            open="",
            partial="  Less: amount already remitted     {paid:m5}\n  Balance to be remitted            {balance:m5}",
        ),
        pay=dict(open="Remittance by bank transfer to the school account only."),
        fraud=["amount_inflation", "identity_mismatch", "institution_mismatch"],
        legit_special="partial_goal", border=["no_documents", "ambiguous_identity"],
    ),
    dict(
        key="school_fees_arrears", category="EDUCATION", split="tune", age_base=12,
        source="school_arrears_statement_and_principal_letter", base_total=54000,
        inst="Gyanodaya Public School", inst_short="Gyanodaya Public School, Patna",
        inst_alt="Little Scholars Academy", city="Patna", state="Bihar", staff="Mrs. Rekha Sinha",
        service="Class VIII", service_alt="Class III", pid_fmt="GPS/ADM/{n}",
        title="Clear school fee arrears for {person_first}",
        story=("{person} studies in Class VIII at {inst}, {city}. After {person_first}'s father passed away last "
               "winter the fees went unpaid for three quarters and the school has said the child cannot sit the "
               "annual examination until arrears are cleared. The arrears statement shows {story_total:m0}; we are "
               "asking for {goal:m0}.{story_extra}"),
        docs=[
            ("FEE_ARREARS_STATEMENT", "Fee arrears statement", """{inst}
STATEMENT OF OUTSTANDING FEES
Statement date: {d_issue:d1}

Student: {person}
Admission No.: {pid}
Class: {service}
Parent: {guardian}

Quarter II  (Jul-Sep)   {i1:m5}
Quarter III (Oct-Dec)   {i2:m5}
Quarter IV  (Jan-Mar)   {i3:m5}
Transport and late fee  {i4:m5}
Total outstanding: {total:m0}
{status_line}"""),
            ("PRINCIPAL_LETTER", "Letter from the principal", """{inst}, {city}
{d_start:d2}

To whom it may concern,

{person} (Admission No. {pid}) has been a student of this school since nursery and is presently in {service}. The
family has been unable to pay the school fees since the death of the child's father. The school will permit the
child to appear for the annual examination once the pending fees are cleared.

{staff}
Principal"""),
        ],
        thin_doc=("OTHER", "Fee note", """School fees pending for {person}: {total:m0}.
Please pay at the earliest.

(handwritten slip, no school name, seal or admission number)"""),
        status=dict(
            open="",
            provisional=("Unaudited working sheet - the accounts office has not yet verified these figures and a "
                         "confirmed statement is awaited."),
        ),
        pay=dict(open=""),
        date_break=(0, "d_issue", "ref", 75),  # statement dated after the appeal was submitted
        keep_when_missing=[1], id_doc=1,
        fraud=["id_mismatch", "date_impossible", "thin_evidence"],
        legit_special="missing_required", border=["provisional", "modest_excess"],
    ),
    dict(
        key="overseas_masters_deposit", category="EDUCATION", split="validation",
        source="university_offer_letter_and_deposit_invoice", base_total=420000,
        inst="Northfield University", inst_short="Northfield Univ.",
        inst_alt="Eastbrook College of Business", city="Lucknow", state="Uttar Pradesh",
        staff="Helen Marsh", service="MSc Public Health (one-year taught programme)",
        service_alt="Foundation Certificate in Hospitality", pid_fmt="NU-{n}-PG",
        title="Tuition deposit for {person_first}'s master's degree",
        story=("{person}, a community health worker from {city}, has an offer to study public health at {inst} in "
               "the United Kingdom. To hold the place and apply for a visa, a tuition deposit must be paid this "
               "month. The university's invoice works out to {story_total:m0}. We are raising {goal:m0}."
               "{story_extra}"),
        docs=[
            ("OFFER_LETTER", "University offer letter", """{inst}
Postgraduate Admissions Office

{d_start:d4}

Dear {person},

Applicant reference: {pid}

We are delighted to offer you a place on the {service}, starting in January 2027. This offer is conditional on
payment of the tuition deposit by {d_due:d4}. {status_line}

Yours sincerely,
{staff}
Head of Postgraduate Admissions"""),
            ("DEPOSIT_INVOICE", "Tuition deposit invoice", """{inst} - Student Finance
TUITION DEPOSIT INVOICE {n}/DEP
Invoice date: {d_issue:d6}
Billed to: {person} (applicant reference {pid})
Programme: {service}

Deposit due: GBP 4,000.00
Equivalent at the indicative rate: {total:m2}
{pay_line}"""),
        ],
        status=dict(
            open="Your place will be confirmed once the deposit is received.",
            provisional=("Please note that this is an invitation to complete your application and not yet a formal "
                         "offer: your academic transcripts are still awaited and no place has been confirmed."),
            ineligible=("We regret that, as the acceptance deadline passed without a response, this offer was "
                        "withdrawn on {d_issue:d4} and the applicant no longer holds a place on the programme."),
        ),
        pay=dict(
            open=("Pay only through the University's online payment portal. The University does not accept "
                  "payments through agents or personal accounts."),
            diverted=("For applicants from India the deposit may be routed through our authorised representative: "
                      "account name {other_person}, SB account 3344{n}019, IFSC ICIC0000{n}."),
        ),
        fraud=["ineligible", "amount_inflation", "payment_diversion"],
        legit_special="high_cost", border=["no_documents", "provisional"],
    ),
    dict(
        key="coaching_and_exam_fees", category="EDUCATION", split="validation",
        source="coaching_academy_invoice_and_enrolment_confirmation", base_total=142000,
        inst="Pinnacle Civil Services Academy", inst_short="Pinnacle CS Academy",
        inst_alt="Bright Future Spoken English Centre", city="Delhi", state="Delhi", staff="Neeraj Bansal",
        service="UPSC General Studies foundation course (12 months)",
        service_alt="Weekend spoken English course (6 weeks)", pid_fmt="PCSA26{n}",
        title="Civil services coaching for {person_first}",
        story=("{person} is the child of a vegetable vendor and cleared the entrance test for the foundation "
               "batch at {inst}, {city}. The family can manage room rent but not the coaching fee. The academy's "
               "invoice is for {story_total:m0}; we hope to raise {goal:m0}.{story_extra}"),
        docs=[
            ("COACHING_INVOICE", "Coaching fee invoice", """{inst}
Tax Invoice

Invoice no: INV-{n}            Invoice dt: {d_issue:d3}
Name of Candidate: {person}
Enrolment No.: {pid}
Course: {service}

Course fee: {i1:m0}
Study material: {i2:m0}
Test series: {i3:m0}
GST @18%: {i4:m0}
Invoice value: {total:m0}
Amount received: {paid:m0}
Balance due: {balance:m0}
{status_line}"""),
            ("ENROLMENT_CONFIRMATION", "Enrolment confirmation email", """From: admissions@pinnacle-academy.example
Subject: Enrolment confirmation - {pid}
Sent: {d_start:d3}

Dear {person},

Congratulations on clearing our scholarship-cum-entrance test. Your seat in the {service} is reserved under
enrolment number {pid}. Classes begin next month at our {city} centre. Please complete the fee payment by
{d_due:d3} to retain the seat.

Regards,
{staff}
Centre Head, {inst}"""),
        ],
        status=dict(
            open="",
            settled="Remarks: fee paid in full by sponsor (corporate CSR scholarship); receipt issued.",
            partial="Remarks: first instalment received.",
        ),
        pay=dict(open=""),
        fraud=["identity_mismatch", "already_settled", "consistent_fabricated"],
        legit_special="partial_paid", border=["ambiguous_identity", "modest_excess"],
    ),
    # ============================ COMMUNITY ==============================
    dict(
        key="village_borewell", category="COMMUNITY", split="tune",
        source="driller_quotation_panchayat_resolution_and_society_certificate", base_total=236000,
        inst="Jal Sahyog Gram Vikas Samiti", inst_short="Jal Sahyog G.V. Samiti",
        inst_alt="Shri Ganesh Krida Mandal", city="Khedgaon", state="Maharashtra", staff="Shri Baban Thorat",
        service="drilling and commissioning of a community borewell with hand pump",
        service_alt="supply of sound system and stage lighting", pid_fmt="MH/2019/{n:07d}", inst_doc=2,
        organisation=True,
        title="A drinking-water borewell for Khedgaon",
        story=("Women in Khedgaon walk nearly two kilometres for drinking water every summer. {inst}, our "
               "registered village society, wants to drill a community borewell beside the anganwadi that will "
               "serve about 140 households. The driller's quotation is {story_total:m0} and we are raising "
               "{goal:m0}.{story_extra}"),
        docs=[
            ("VENDOR_QUOTATION", "Borewell driller quotation", """Shree Balaji Borewells & Pumps
Market Yard Road, Ahmednagar

QUOTATION                         Quotation No: SBB/{n}        Date: {d_issue:d0}
To: The Secretary, {inst}, {city}
Work: {service}

  Drilling 300 ft @ site                 {i1:m5}
  Casing pipe and gravel packing         {i2:m5}
  Hand pump with platform                {i3:m5}
  Transport and labour                   {i4:m5}
Total quotation value: {total:m1}
Validity: 60 days. 50% advance with work order.
{pay_line}"""),
            ("PANCHAYAT_RESOLUTION", "Gram panchayat resolution", """Gram Panchayat Khedgaon, Taluka Shrigonda
Extract of resolution no. 14 passed in the Gram Sabha held on {d_start:d2}

Resolved that {inst} (Registration No. {pid}) be permitted to carry out {service} on panchayat land near the
anganwadi for the benefit of about 140 households of wards 2 and 3. {status_line}

Sarpanch, Gram Panchayat Khedgaon"""),
            ("SOCIETY_REGISTRATION", "Society registration certificate", """CERTIFICATE OF REGISTRATION
(Societies Registration Act, 1860)

Name of Society: {inst}
Registration No.: {pid}
Registered office: {city}, District Ahmednagar
Date of registration: 12/08/2019
President: {staff}

Assistant Registrar of Societies"""),
        ],
        status=dict(
            open="The society shall maintain the borewell and submit accounts to the Gram Sabha.",
            settled=("The Sabha noted that the borewell at the said site has since been completed and fully paid "
                     "for under the Jal Jeevan Mission (work order JJM/{n}); no further funds are required for this work."),
            provisional=("This resolution is in-principle only: the no-objection certificate from the Groundwater "
                         "Department is awaited and work may not begin until it is received."),
        ),
        pay=dict(open="Payment by account payee cheque in the name of the firm."),
        fraud=["already_settled", "institution_mismatch", "amount_inflation"],
        legit_special="partial_goal", border=["provisional", "no_documents"],
    ),
    dict(
        key="flood_relief_kits", category="COMMUNITY", split="tune",
        source="wholesaler_proforma_trust_certificate_and_ward_summary", base_total=690000,
        inst="Asha Kiran Charitable Trust", inst_short="Asha Kiran Trust",
        inst_alt="Barak Sports and Cultural Club", city="Silchar", state="Assam", staff="Mrs. Dipali Nath",
        service="600 family relief kits (rice, dal, oil, tarpaulin, water purification tablets)",
        service_alt="banquet catering for 600 guests", pid_fmt="CAC/TR/{n}/2017", id_doc=0, organisation=True,
        title="Relief kits for flood-hit families in Silchar",
        story=("Three low-lying wards of {city} were under water for nine days this monsoon and hundreds of "
               "families lost their stored grain and bedding. {inst} has been running a community kitchen and now "
               "plans to distribute 600 family relief kits. The wholesaler's proforma invoice totals "
               "{story_total:m0}; the appeal target is {goal:m0}.{story_extra}"),
        docs=[
            ("PROFORMA_INVOICE", "Relief kit proforma invoice", """Barak Valley Wholesale Traders
Fatak Bazar, {city}
PROFORMA INVOICE          PI No. {n}/26-27          Dt. {d_issue:d1}

Buyer: {inst}
Buyer's Trust Regn. No.: {pid}
Supply of: {service}

Qty 600 kits
  Dry ration per kit lot           {i1:m5}
  Tarpaulin sheets                 {i2:m5}
  Hygiene and purification items   {i3:m5}
  Packing and delivery             {i4:m5}
Grand Total (incl. taxes): {total:m2}
{pay_line}"""),
            ("TRUST_REGISTRATION", "Trust registration and tax certificate", """Office of the Sub-Registrar, Cachar
This is to certify that {inst} is a public charitable trust registered at this office.
Trust Regn. No.: {pid}
Managing Trustee: {staff}
PAN: AAATA{n}K        12A/80G: available
{status_line}"""),
            ("BENEFICIARY_SUMMARY", "Ward-wise beneficiary summary", """{inst} - Flood response 2026
Ward-wise list of affected households identified with ward commissioners (summary), prepared {d_start:d1}

Ward 11 (Tarapur): 230 households
Ward 14 (Malugram): 195 households
Ward 22 (Rangirkhari): 175 households
Total households: 600
One kit per household; the detailed name list is held at the trust office."""),
        ],
        status=dict(
            open="Status: registration in force.",
            provisional=("Status: application for registration received; the certificate has not yet been issued "
                         "and verification is pending."),
            ineligible=("STATUS: registration CANCELLED by order dated {d_start:d1}; the trust is not authorised "
                        "to solicit donations."),
        ),
        pay=dict(open="Payment terms: 100% by RTGS to the supplier before dispatch."),
        solicit=(" For faster relief, well-wishers may also transfer straight into our treasurer's own savings "
                 "account; the details will be shared over WhatsApp on request."),
        fraud=["payment_diversion", "ineligible", "id_mismatch"],
        legit_special="high_cost", border=["modest_excess", "provisional"],
    ),
    dict(
        key="school_toilet_block", category="COMMUNITY", split="tune",
        source="contractor_abstract_and_school_committee_minutes", base_total=318000,
        inst="Navjyoti Shiksha Samiti", inst_short="Navjyoti Shiksha Samiti (SMC)",
        inst_alt="Maruti Vyapar Mandal", city="Bhilwara", state="Rajasthan", staff="Smt. Kamla Meena",
        service="construction of a girls' toilet block with water connection",
        service_alt="painting of the boundary wall and compound gate", pid_fmt="RAJ/SMC/{n}", svc_doc=0,
        organisation=True,
        title="Girls' toilet block for the government school in Bhilwara",
        story=("The government upper primary school in our mohalla has 210 girls and one broken toilet, and many "
               "girls stop coming after Class VI. {inst}, the school management committee society, has resolved to "
               "build a proper girls' toilet block with running water. The contractor's estimate is "
               "{story_total:m0}. We are raising {goal:m0}.{story_extra}"),
        docs=[
            ("CONTRACTOR_ESTIMATE", "Contractor's abstract of cost", """Marudhar Constructions
Civil contractors, {city}

ABSTRACT OF COST                       Est. No. MC/{n}       {d_issue:d2}
Client: {inst}, Govt. Upper Primary School, {city}
Name of work: {service}

  Excavation, foundation and plinth    {i1:m5}
  Brickwork, roofing and plaster       {i2:m5}
  Sanitary fittings and plumbing       {i3:m5}
  Overhead tank and water connection   {i4:m5}
Total: {total:m0}
{status_line}"""),
            ("SMC_MINUTES", "School management committee minutes", """{inst}
Minutes of the committee meeting held on {d_start:d2} at the school premises
Society registration: {pid}
Present: {staff} (Chairperson), the headmaster and nine members.

Item 3: The committee discussed the lack of usable toilets for girl students. It was unanimously resolved to take
up {service} and to raise funds from well-wishers for the purpose. The headmaster will supervise the work and the
accounts will be placed before the next meeting.

Chairperson"""),
        ],
        status=dict(
            open="",
            partial="Mobilisation advance received: {paid:m0}. Balance on completion: {balance:m0}.",
        ),
        pay=dict(open=""),
        date_break=(1, "d_start", "ref", 60),  # minutes of a meeting dated after the appeal
        fraud=["date_impossible", "service_mismatch", "consistent_fabricated"],
        legit_special="partial_paid", border=["no_documents", "modest_excess"],
    ),
    dict(
        key="women_tailoring_centre", category="COMMUNITY", split="validation",
        source="machine_dealer_quotation_federation_letter_and_bank_letter", base_total=184000,
        inst="Ujjwala Mahila Swayam Sahayata Samuh", inst_short="Ujjwala Mahila SHG",
        inst_alt="Vaigai Auto Drivers Welfare Sangam", city="Madurai", state="Tamil Nadu",
        staff="Tmt. Selvi Murugan", service="12 industrial sewing machines and 2 overlock machines",
        service_alt="one second-hand passenger autorickshaw", pid_fmt="TN/MDU/SHG/{n}", id_doc=2,
        organisation=True,
        title="Sewing machines for a women's tailoring centre",
        story=("We are fourteen women from a weavers' colony in {city} who formed {inst} four years ago. We stitch "
               "school uniforms on borrowed machines and want to set up our own tailoring centre so that more "
               "women can earn from home. The dealer's quotation for the machines is {story_total:m0}; our target "
               "is {goal:m0}.{story_extra}"),
        docs=[
            ("MACHINE_QUOTATION", "Sewing machine quotation", """Sri Meenakshi Sewing Machine Agencies
West Masi Street, {city}

Qtn. No. SM/{n}                                   Dt: {d_issue:d5}
Kind Attn: The Animator, {inst}
Sub: Quotation for {service}

Industrial single-needle machines (12 nos)   {i1:m5}
Overlock machines (2 nos)                    {i2:m5}
Tables, stands and motors                    {i3:m5}
Installation and one-year service            {i4:m5}
Net amount: {total:m3}
{pay_line}"""),
            ("FEDERATION_LETTER", "Federation membership letter", """Madurai District Mahalir Federation
{d_start:d5}

Certified that {inst}, Regd. No. {pid}, is a member group of this federation with {staff} as its animator. The
group has fourteen members and holds regular savings meetings. {status_line}

Federation Coordinator"""),
            ("BANK_LETTER", "Bank account confirmation", """Pandyan Grama Bank, Sellur Branch
Ref: PGB/SEL/{n}        {d_issue:d5}

This is to confirm that a savings bank account is maintained with this branch in the name of {inst}
(Regd. No. {pid}), operated jointly by the animator and the representative. {bank_line}

Branch Manager"""),
        ],
        status=dict(
            open="The group was graded 'A' in the last audit.",
            provisional=("The group's renewal papers are under scrutiny and its membership for the current year "
                         "has not yet been confirmed."),
            ineligible=("However, the group became defunct last year and its registration has been cancelled; this "
                        "federation no longer recognises it as a member."),
            partial="The group was graded 'A' in the last audit.",
        ),
        bank=dict(
            open="No loan is outstanding against the group.",
            partial=("A term loan of {paid:m3} has been sanctioned towards purchase of machines; the group must "
                     "arrange the remaining {balance:m3} as its own contribution."),
        ),
        pay=dict(
            open="Payment: cheque/NEFT in the name of the agency against delivery.",
            diverted=("Advance to be transferred to: {other_person}, personal SB a/c 6021{n}55, to block the stock."),
        ),
        fraud=["payment_diversion+ineligible", "amount_inflation", "id_mismatch"],
        legit_special="partial_paid", border=["provisional", "no_documents"],
    ),
    dict(
        key="library_reading_room", category="COMMUNITY", split="validation",
        source="bookseller_estimate_and_youth_club_certificate", base_total=127000,
        inst="Pragati Yuva Mandal", inst_short="Pragati Yuvak Mandal",
        inst_alt="Hubballi Traders Recreation Association", city="Dharwad", state="Karnataka",
        staff="Sri Manjunath Hiremath", service="books, steel racks and reading tables for a village library",
        service_alt="cricket kits and team jerseys", pid_fmt="DWD-S{n}-2018", inst_doc=1, organisation=True,
        title="A reading room for students in our village",
        story=("Students in our village near {city} prepare for competitive examinations under streetlights "
               "because there is no library within twenty kilometres. {inst}, our youth club, has been given a "
               "room by the panchayat and wants to furnish it as a free reading room. The bookseller's estimate is "
               "{story_total:m0} and we wish to raise {goal:m0}.{story_extra}"),
        docs=[
            ("BOOKSELLER_ESTIMATE", "Bookseller's estimate", """Sapna Granth Bhandar
Subhas Road, {city}

ESTIMATE No. {n}                                   Date: {d_issue:d3}
M/s. {inst}

For supply of {service}:
  Competitive examination books (410 titles)   {i1:m5}
  Reference and general reading (250 titles)   {i2:m5}
  Steel racks (6)                              {i3:m5}
  Reading tables and chairs                    {i4:m5}
Estimate amount (inclusive of discount): {total:m4}
{status_line}"""),
            ("SOCIETY_CERTIFICATE", "Youth club registration certificate", """Government of Karnataka - Department of Co-operation
Certificate under the Karnataka Societies Registration Act, 1960

It is certified that {inst}, {city} taluk, has this day been registered as a society.
Registration number: {pid}
President: {staff}

District Registrar of Societies"""),
        ],
        thin_doc=("OTHER", "Budget note", """Library budget

Books and furniture for the reading room: {total:m0} approx.

(plain typed sheet; no supplier name, estimate number or signature)"""),
        status=dict(
            open="Delivery within three weeks of confirmed order.",
            settled=("Note: the books and furniture listed in this estimate were supplied on {d_start:d3} and the "
                     "bill was paid in full from the Zilla Panchayat library grant."),
            provisional=("Rough indicative list only - titles and quantities are yet to be finalised with the "
                         "club and this is not a confirmed estimate."),
        ),
        pay=dict(open=""),
        keep_when_missing=[1],
        fraud=["already_settled", "institution_mismatch", "thin_evidence"],
        legit_special="missing_required", border=["modest_excess", "provisional"],
    ),
]

# What an ideal dossier-only reviewer could conclude for each variant.
VARIANT_META = {
    # variant: (planted inconsistency kinds, expected action, detectable from dossier alone)
    "clean": ([], "APPROVED", None),
    "harmless_formatting": ([], "APPROVED", None),
    "partial_paid": ([], "APPROVED", None),
    "partial_goal": ([], "APPROVED", None),
    "high_cost": ([], "APPROVED", None),
    "estimate_revision": ([], "APPROVED", None),
    "missing_required": ([], "NEEDS_MORE_INFORMATION", None),
    "identity_mismatch": (["identity"], "FLAG_FOR_REVIEW", True),
    "already_settled": (["settlement"], "FLAG_FOR_REVIEW", True),
    "amount_inflation": (["amount"], "FLAG_FOR_REVIEW", True),
    "date_impossible": (["chronology"], "FLAG_FOR_REVIEW", True),
    "id_mismatch": (["identifier"], "FLAG_FOR_REVIEW", True),
    "institution_mismatch": (["institution"], "FLAG_FOR_REVIEW", True),
    "payment_diversion": (["payment_routing"], "FLAG_FOR_REVIEW", True),
    "service_mismatch": (["service"], "FLAG_FOR_REVIEW", True),
    "ineligible": (["eligibility"], "FLAG_FOR_REVIEW", True),
    "consistent_fabricated": ([], "FLAG_FOR_REVIEW", False),
    "thin_evidence": ([], "NEEDS_MORE_INFORMATION", False),
    "no_documents": ([], "NEEDS_MORE_INFORMATION", None),
    "provisional": ([], "NEEDS_MORE_INFORMATION", None),
    "modest_excess": ([], "NEEDS_MORE_INFORMATION", None),
    "ambiguous_identity": ([], "NEEDS_MORE_INFORMATION", None),
}
NOTES = {
    "clean": "Need, identity, institution and amount are supported by the dossier.",
    "harmless_formatting": "Same facts as a clean dossier; one document renders the name, dates, amounts, institution and identifier in a different but equivalent style.",
    "partial_paid": "Part of the cost is already paid or covered and the appeal is only for the documented balance.",
    "partial_goal": "The appeal asks for less than the documented cost.",
    "high_cost": "Unusually high cost that is fully supported by the cost document.",
    "estimate_revision": "An earlier, lower estimate was superseded by a later revised estimate; the appeal matches the revision.",
    "missing_required": "Genuine need, but the cost document was not uploaded; more information is the right outcome.",
    "identity_mismatch": "A core document is in another person's name.",
    "already_settled": "A document shows the expense was already paid, waived or fully funded by a scheme.",
    "amount_inflation": "The appeal and story claim far more than the cost document supports.",
    "date_impossible": "Document dates are chronologically impossible for the claimed sequence of events.",
    "id_mismatch": "The same identifier differs between documents from the same institution.",
    "institution_mismatch": "A core document was issued by or to a different institution than the one claimed.",
    "payment_diversion": "Funds are directed to an unrelated individual's personal account.",
    "service_mismatch": "The treatment, course or work described differs between the claim and a core document.",
    "ineligible": "An institutional record shows the enrolment, offer or registration was cancelled or withdrawn.",
    "consistent_fabricated": "All paperwork is fabricated but mutually consistent; nothing in the dossier reveals it. Detectable only by contacting the issuer.",
    "thin_evidence": "A fabricated appeal backed only by an unattributable note; a dossier-only reviewer can ask for proper documents but cannot establish fraud.",
    "no_documents": "No supporting documents were uploaded; the claim is unresolved.",
    "provisional": "The key document is provisional, draft or awaiting an approval; the claim is unresolved.",
    "modest_excess": "The appeal is modestly above the documented cost with an undocumented explanation.",
    "ambiguous_identity": "One document carries the same given name with a different surname; a plausible explanation is offered but unverified.",
}
EXCESS_EXPLANATIONS = [
    " The amount also covers travel and medicines after the main expense, for which we do not have bills yet.",
    " We have added a little for incidental costs that are not on the paperwork.",
    " The extra over the document is for local transport and small purchases we expect along the way.",
]


def name_variant(person, style):
    parts = person.split()
    if style % 3 == 0:
        return " ".join(f"{p[0]}." for p in parts[:-1]) + " " + parts[-1]
    if style % 3 == 1:
        return f"{parts[-1].upper()} {' '.join(parts[:-1]).upper()}"
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def build_case(family, family_index, slot):
    label = "legitimate" if slot < 3 else "fraudulent" if slot < 6 else "borderline"
    variant = (["clean", "harmless_formatting", family["legit_special"]] + family["fraud"] + family["border"])[slot]
    seq = family_index * 8 + slot
    n = 1040 + 37 * seq
    last = LAST[(7 * seq + 3) % len(LAST)]
    first = FIRST[seq % len(FIRST)]
    person = f"{first} {MIDDLE[seq % len(MIDDLE)]} {last}" if seq % 3 == 0 else f"{first} {last}"
    other_first = FIRST[(seq + 7) % len(FIRST)]
    other_person = f"{other_first} {LAST[(7 * seq + 14) % len(LAST)]}"
    organisation = family.get("organisation", False)
    ref = REFERENCE_DATE + timedelta(days=seq % 9)
    offsets = family.get("dates", dict(d_start=-20, d_issue=-12, d_end=25, d_due=30))
    total = int(round(family["base_total"] * (1 + 0.06 * slot) * (3 if variant == "high_cost" else 1), -3))

    facts = dict(
        n=n, person=person, person_first=first, guardian=f"{FIRST[(seq + 11) % len(FIRST)]} {last}",
        other_person=other_person, upi=f"{other_first.lower()}{n}@okhdfc", age=family.get("age_base", 30) + slot * 3,
        inst=family["inst"], city=family["city"], staff=family["staff"], service=family["service"],
        pid=family["pid_fmt"].format(n=n), total=total, paid=0, covered=0, balance=total, goal=total,
        story_total=total, old_total=int(round(total * 0.8, -3)), story_extra="", shift=0,
        **{key: ref + timedelta(days=days) for key, days in offsets.items()},
    )
    state = dict(status="open", pay="open", bank="open", docs=list(range(len(family["docs"]))), extra_docs=[])
    doc_over = {index: {} for index in range(len(family["docs"]) + 1)}
    story_over = {}
    target = 1 if len(family["docs"]) > 1 else 0

    for part in variant.split("+"):
        if part == "harmless_formatting":
            doc_over[target].update(
                person=person if organisation else name_variant(person, family_index), shift=2,
                inst=family["inst_short"], pid=facts["pid"].replace("/", "-").lower())
        elif part == "partial_paid":
            facts["paid"] = int(round(total * 0.3, -3))
            facts["balance"] = facts["goal"] = total - facts["paid"]
            state["status"] = state["bank"] = "partial"
            facts["story_extra"] = (" Part of the amount has already been arranged and paid; this appeal is only "
                                    "for the remaining balance shown in the papers.")
        elif part == "partial_goal":
            facts["goal"] = int(round(total * 0.6, -3))
            facts["story_extra"] = " We are arranging the rest ourselves through relatives and a small loan."
        elif part == "estimate_revision":
            state["extra_docs"].append(family["revision_doc"])
            facts["story_extra"] = (" The first estimate was lower, but the surgeon revised it after deciding that "
                                    "navigation-guided implants are needed.")
        elif part == "missing_required":
            state["docs"] = family["keep_when_missing"]
        elif part == "identity_mismatch":
            wrong = f"{other_first} {last}" if family.get("relative_mismatch") else other_person
            doc_over[target]["person"] = wrong
        elif part == "already_settled":
            state["status"] = "settled"
            facts.update(paid=total, balance=0)
        elif part == "amount_inflation":
            facts["goal"] = story_over["story_total"] = int(round(total * 2.3, -3))
        elif part == "date_impossible":
            index, key, anchor, days = family["date_break"]
            doc_over[index][key] = (ref if anchor == "ref" else facts[anchor]) + timedelta(days=days)
        elif part == "id_mismatch":
            doc_over[family.get("id_doc", target)]["pid"] = family["pid_fmt"].format(n=n + 3311)
        elif part == "institution_mismatch":
            doc_over[family.get("inst_doc", target)]["inst"] = family["inst_alt"]
        elif part == "payment_diversion":
            if "diverted" in family["pay"]:
                state["pay"] = "diverted"
            else:
                facts["story_extra"] = family["solicit"]
        elif part == "service_mismatch":
            doc_over[family.get("svc_doc", target)]["service"] = family["service_alt"]
        elif part == "ineligible":
            state["status"] = "ineligible"
        elif part == "thin_evidence":
            state["docs"], state["extra_docs"] = [], [family["thin_doc"]]
        elif part == "no_documents":
            state["docs"] = []
        elif part == "provisional":
            state["status"] = "provisional"
            state["docs"] = family.get("provisional_keep", state["docs"])
        elif part == "modest_excess":
            facts["goal"] = int(round(total * 1.22, -3))
            facts["story_extra"] = EXCESS_EXPLANATIONS[family_index % len(EXCESS_EXPLANATIONS)]
        elif part == "ambiguous_identity":
            doc_over[target]["person"] = f"{first} {LAST[(7 * seq + 8) % len(LAST)]}"
            facts["story_extra"] = (f" Some of the papers carry {first}'s name with the surname used in older "
                                    "family records.")

    for index, fraction in enumerate((0.14, 0.46, 0.25), start=1):
        facts[f"i{index}"] = int(round(total * fraction, -2))
    facts["i4"] = total - facts["i1"] - facts["i2"] - facts["i3"]

    def view(overrides):
        merged = {**facts, **overrides}
        for slot_name, table in (("status_line", "status"), ("pay_line", "pay"), ("bank_line", "bank")):
            phrases = family.get(table, {})
            merged[slot_name] = render(phrases.get(state[table], phrases.get("open", "")), merged) if phrases else ""
        return merged

    documents = []
    for index in state["docs"]:
        doc_type, title, template = family["docs"][index]
        documents.append({"doc_type": doc_type, "title": title, "content": render(template, view(doc_over[index]))})
    for doc_type, title, template in state["extra_docs"]:
        documents.append({"doc_type": doc_type, "title": title, "content": render(template, view({}))})

    planted, expected, detectable = [], None, None
    for part in variant.split("+"):
        kinds, expected, part_detectable = VARIANT_META[part]
        planted += kinds
        detectable = part_detectable if detectable is None else (detectable or part_detectable)
    story_view = view(story_over)
    return {
        "case_id": f"DV2-{seq + 1:03d}", "ground_truth": label, "variant": variant,
        "scenario_family": family["key"], "document_source": family["source"], "split": family["split"],
        "planted_inconsistencies": planted, "expected_action": expected,
        "detectable_from_dossier": detectable, "synthetic": True,
        "adjudication_note": " ".join(NOTES[part] for part in variant.split("+")),
        "input": {
            "title": render(family["title"], story_view), "category": family["category"],
            "story": render(family["story"], story_view), "goal_amount": facts["goal"],
            "beneficiary_name": family["inst"] if organisation else person,
            "beneficiary_type": "ORGANISATION" if organisation else "SELF",
            "city": family["city"], "state": family["state"], "submitted_on": ref.isoformat(),
            "documents": documents,
        },
    }


def make_cases():
    return [build_case(family, index, slot) for index, family in enumerate(FAMILIES) for slot in range(8)]


if __name__ == "__main__":
    rows = make_cases()
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"Wrote {len(rows)} synthetic scenarios to {OUT}")
