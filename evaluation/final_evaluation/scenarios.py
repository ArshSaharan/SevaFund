"""60 developer-designed synthetic scenarios for the final offline evaluation (not independent validation).

Written for this evaluation by the developer of the system under test, after the hybrid v4 changes were made and
before any system was run on them.  They are new text (not copied from the 750 benchmark cases or earlier sets), but
the author knows how the systems work, so results are optimistic in an unknown direction and are NOT independent
evidence.  Every name, institution, phone number and account number is invented.

Strata (truth is set by construction):
  FD  15 fraud detectable from the documents (contradictions, inflation visible in the documents, settled bills ...)
  FS  10 sophisticated fraud: internally consistent documents; only an independent party can reveal it
         (including 1 collusive case that no independent party reveals)
  LC  15 legitimate, complete documentation
  LI  10 legitimate, incomplete documentation (5 genuine applicants without a formal quotation)
  BC  10 borderline or contradictory: a careful reviewer would need more information

Each scenario carries a scripted Gemini response (fixed before any run, identical for every system), and an external
environment describing what each independent party would say if contacted through its own official channel.  The
Gemini script is deliberately imperfect: it misses some fraud, raises one false alarm, raises unquoted suspicions,
and fails on 4 cases.
"""
import json
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
OUT = HERE / "scenarios.jsonl"


def inr(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts + [tail])


def D(title: str, doc_type: str, content: str) -> dict:
    return {"title": title, "doc_type": doc_type, "content": content}


def env(ben="CONFIRMED", inst="CONFIRMED", pay="CONFIRMED", issuer="CONFIRMED", stated=None, other=0,
        supplied: Optional[dict] = None, note: str = "") -> dict:
    out = {"BENEFICIARY": {"independent_response": ben}, "INSTITUTION": {"independent_response": inst},
           "PAYMENT_DESTINATION": {"independent_response": pay},
           "COST_ISSUER": {"independent_response": issuer, "amount_stated_inr": stated, "other_payers_inr": other},
           "note": note}
    for party, response in (supplied or {}).items():
        out[party]["campaign_supplied_contact"] = {"printed_in_uploads": True, "response": response}
    return out


def approve():
    return {"kind": "approve"}


def nmi(*missing):
    return {"kind": "nmi", "missing": list(missing) or ["A supporting document is needed."]}


def flag(category, description, document, quote):
    return {"kind": "flag", "category": category, "description": description, "document": document, "quote": quote}


def flag_unquoted(description, recommendation="FLAG_FOR_REVIEW"):
    return {"kind": "flag_unquoted", "description": description, "recommendation": recommendation}


def failure(category):
    return {"kind": "failure", "category": category}   # SERVER_ERROR | READ_TIMEOUT | invalid_json | truncated


SCENARIOS: List[dict] = []


def S(cid, stratum, label, documentation, category, title, story, goal, name, btype, city, state, submitted, docs,
      environment, gemini, mechanism=None, subtype=None, note=""):
    SCENARIOS.append({
        "case_id": cid, "stratum": stratum, "truth_label": label, "documentation": documentation, "category": category,
        "mechanism": mechanism, "incomplete_subtype": subtype, "detectable_from_documents": stratum == "FD",
        "scenario_note": note, "developer_designed": True, "synthetic": True,
        "input": {"title": title, "category": category, "story": story, "goal_amount": goal, "goal_currency": "INR",
                  "beneficiary_name": name, "beneficiary_type": btype, "city": city, "state": state,
                  "submitted_on": submitted, "documents": docs},
        "external_environment": environment, "gemini_script": gemini})


# =====================================================================================================================
# LC: legitimate, complete (15)
# =====================================================================================================================
S("FE-LC-MED-01", "LC", "legitimate", "complete", "MEDICAL", "Hip surgery for Kamala Bai",
  "Kamala Bai, 68, fell at home and fractured her left hip. Sushruta Hospital in Nagpur will fix it with a hemiarthroplasty "
  "next week. Her son is a daily-wage painter. The estimate and the doctor's note are attached.",
  185000, "Kamala Bai", "SELF", "Nagpur", "Maharashtra", "2026-11-14",
  [D("Hospital estimate", "HOSPITAL_ESTIMATE",
     "Sushruta Hospital, Wardha Road, Nagpur 440015. Estimate No. SH/EST/26/4471 Date: 11/11/2026\nPatient: Kamala Bai, 68 F, "
     "UHID SH-208813\nProcedure: Left hip hemiarthroplasty\nImplant Rs 75,000; Surgery and OT Rs 55,000; Ward 4 days Rs 32,000; "
     "Medicines Rs 23,000\nTotal estimate Rs 1,85,000. Planned surgery date: 21/11/2026. Billing Executive (signed)"),
   D("Orthopaedic note", "CLINICAL_NOTE",
     "Sushruta Hospital casualty 10/11/2026. Kamala Bai 68 F. Displaced fracture neck of left femur after a fall at home. "
     "Advised hemiarthroplasty. Dr P. Wankhede MS Ortho")],
  env(stated=185000), approve())

S("FE-LC-MED-02", "LC", "legitimate", "complete", "MEDICAL", "Chemotherapy for Arjun",
  "Arjun Nair is 34 and was diagnosed with Hodgkin lymphoma in October. Malabar Cancer Care has planned six cycles of "
  "chemotherapy. He works as a bus conductor and his savings are gone after the scans.",
  240000, "Arjun Nair", "SELF", "Kannur", "Kerala", "2026-11-05",
  [D("Chemotherapy estimate", "HOSPITAL_ESTIMATE",
     "Malabar Cancer Care, Thalassery Road, Kannur. Estimate MCC/ONC/2026/918 dated 02/11/2026. Patient Arjun Nair 34 M, "
     "MRN MCC-55120. ABVD chemotherapy, 6 cycles at Rs 40,000 per cycle including day-care charges. Total Rs 2,40,000. "
     "Accounts Officer (signed)"),
   D("Oncology summary", "CLINICAL_NOTE",
     "Malabar Cancer Care, Department of Medical Oncology. 30/10/2026. Arjun Nair 34 M, MRN MCC-55120. Classical Hodgkin "
     "lymphoma stage IIA on biopsy and PET-CT. Plan: ABVD x 6 cycles. Dr R. Menon DM Oncology")],
  env(stated=240000), approve())

S("FE-LC-MED-03", "LC", "legitimate", "complete", "MEDICAL", "Kidney stone surgery balance for Farida",
  "Farida Begum, 45, needs surgery for a large kidney stone. Her insurance has approved part of the cost and we are "
  "raising only the balance that the hospital says she must pay.",
  60000, "Farida Begum", "SELF", "Hyderabad", "Telangana", "2026-10-28",
  [D("Estimate and insurance approval", "HOSPITAL_ESTIMATE",
     "Deccan Urology Centre, Mehdipatnam, Hyderabad. Estimate DUC/E/2026/2207 dated 24/10/2026. Patient Farida Begum 45 F, "
     "UHID DUC-31876. Right PCNL. Package Rs 1,60,000. Insurance pre-authorisation approved Rs 1,00,000. "
     "Balance payable by patient Rs 60,000. Billing Desk (signed)"),
   D("Urology note", "CLINICAL_NOTE",
     "Deccan Urology Centre OPD 22/10/2026. Farida Begum 45 F. 2.4 cm right renal pelvic calculus with hydronephrosis on CT. "
     "Advised right PCNL. Dr S. Qureshi MCh Urology")],
  env(stated=160000, other=100000), approve())

S("FE-LC-MED-04", "LC", "legitimate", "complete", "MEDICAL", "Dialysis access and treatment for Ramesh",
  "Ramesh Patil, 52, has kidney failure. He needs a fistula operation and three months of dialysis while he waits for "
  "a transplant evaluation. He was a school peon and has no savings left.",
  126000, "Ramesh Patil", "SELF", "Pune", "Maharashtra", "2026-10-19",
  [D("Nephrology estimate", "HOSPITAL_ESTIMATE",
     "Indrayani Kidney Hospital, Bhosari, Pune. Estimate IKH/2026/773 dated 15/10/2026. Patient Ramesh Patil 52 M, "
     "UHID IKH-90412. AV fistula surgery Rs 36,000; haemodialysis 36 sessions at Rs 2,500 Rs 90,000. Total Rs 1,26,000. "
     "Cashier (signed)"),
   D("Nephrologist letter", "CLINICAL_NOTE",
     "Indrayani Kidney Hospital. 14/10/2026. Ramesh Patil 52 M. End-stage kidney disease, eGFR 8. Requires AV fistula and "
     "maintenance haemodialysis three times a week. Dr V. Kulkarni DM Nephrology")],
  env(issuer="UNREACHABLE", stated=None), approve(),
  note="The billing desk cannot be reached; a genuine campaign that should stay pending.")

S("FE-LC-MED-05", "LC", "legitimate", "complete", "MEDICAL", "Cataract operations for Gurdeep Kaur",
  "Gurdeep Kaur, 66, can no longer see well enough to cook or walk to the gurdwara. Guru Nanak Eye Hospital will "
  "operate on both eyes. Her husband is a retired tailor.",
  64000, "Gurdeep Kaur", "SELF", "Amritsar", "Punjab", "2026-09-22",
  [D("Eye surgery estimate", "HOSPITAL_ESTIMATE",
     "Guru Nanak Eye Hospital, Majitha Road, Amritsar. Estimate GNEH/26/1180 dated 18/09/2026. Patient Gurdeep Kaur 66 F. "
     "Phacoemulsification with foldable lens, both eyes, Rs 32,000 per eye. Total Rs 64,000. Counter Clerk (seal)"),
   D("Eye examination", "CLINICAL_NOTE",
     "Guru Nanak Eye Hospital OPD 17/09/2026. Gurdeep Kaur 66 F. Bilateral mature cataract, vision 6/60 both eyes. "
     "Advised phacoemulsification. Dr H. Sandhu MS Ophthalmology")],
  env(stated=64000), flag_unquoted("The campaign may exaggerate the need; cataract surgery is often free."),
  note="Scripted false alarm from Gemini without a quote.")

S("FE-LC-EDU-01", "LC", "legitimate", "complete", "EDUCATION", "Second-year nursing fees for Reshma",
  "Reshma Khatun is in the second year of B.Sc Nursing at Ruby Hall College of Nursing. Her father drives a cycle "
  "van. The fee demand and her identity card are attached.",
  105000, "Reshma Khatun", "SELF", "Kolkata", "West Bengal", "2026-10-08",
  [D("Fee demand 2026-27", "FEE_DEMAND",
     "Ruby Hall College of Nursing, Kasba, Kolkata 700107. Accounts Section. Demand No. RHCN/ACC/26/1442 Date 01/10/2026\n"
     "Student: Reshma Khatun, Roll BSN25-061, B.Sc Nursing Year 2. Tuition Rs 85,000; Clinical posting Rs 12,000; "
     "Examination Rs 8,000. Total Rs 1,05,000. Last date for payment: 15/12/2026. Accounts Officer (signed)"),
   D("Student identity card", "IDENTITY",
     "Ruby Hall College of Nursing. Identity card. Reshma Khatun, B.Sc Nursing, Roll BSN25-061, valid till 2029.")],
  env(stated=105000), approve())

S("FE-LC-EDU-02", "LC", "legitimate", "complete", "EDUCATION", "Electrician course for Sandeep",
  "Sandeep Oraon finished class 12 and got a seat in the two-year electrician trade at Chotanagpur Private ITI. His "
  "mother works on a farm. We need the first-year fees.",
  38500, "Sandeep Oraon", "SELF", "Ranchi", "Jharkhand", "2026-09-30",
  [D("ITI fee slip", "FEE_DEMAND",
     "Chotanagpur Private ITI, Kanke Road, Ranchi. Fee slip CPITI/F/2026/0388 dated 24/09/2026. Trainee Sandeep Oraon, "
     "Electrician trade, Session 2026-28, Year 1. Tuition Rs 30,000; Workshop Rs 6,000; Uniform and kit Rs 2,500. "
     "Total Rs 38,500. Office Superintendent (signed)"),
   D("Admission letter", "ADMISSION_LETTER",
     "Chotanagpur Private ITI. Ref CPITI/ADM/26/212 dated 20/09/2026. Sandeep Oraon is admitted to the Electrician trade "
     "for session 2026-28. Principal")],
  env(stated=38500), approve())

S("FE-LC-EDU-03", "LC", "legitimate", "complete", "EDUCATION", "MBA fee balance for Priyanka",
  "Priyanka Rao is in her second semester of the MBA at Godavari Institute of Management. Her merit scholarship pays "
  "part of the fee. We are raising the balance shown on the college statement.",
  95000, "Priyanka Rao", "SELF", "Rajahmundry", "Andhra Pradesh", "2026-11-02",
  [D("Fee statement", "FEE_STATEMENT",
     "Godavari Institute of Management, Rajahmundry. Fee statement GIM/FS/2026/731 dated 28/10/2026. Student Priyanka Rao, "
     "Enrolment No. GIM24MBA077, MBA Semester 2. Semester fee Rs 1,45,000. Merit scholarship credited Rs 50,000. "
     "Balance due Rs 95,000. Accounts Officer (signed)"),
   D("Bonafide certificate", "CERTIFICATE",
     "Godavari Institute of Management. Bonafide certificate. Priyanka Rao, Enrolment No. GIM24MBA077, is a bonafide "
     "student of MBA 2025-27. Registrar")],
  env(stated=145000, other=50000), approve())

S("FE-LC-EDU-04", "LC", "legitimate", "complete", "EDUCATION", "Class 11 fees and books for Tenzin",
  "Tenzin Dolma scored well in class 10 and joined class 11 science at Himalayan Hill School. Her family runs a small "
  "tea stall. The school's fee demand for the year is attached.",
  42000, "Tenzin Dolma", "SELF", "Darjeeling", "West Bengal", "2026-10-15",
  [D("School fee demand", "FEE_DEMAND",
     "Himalayan Hill School, Lebong Cart Road, Darjeeling. Fee demand HHS/2026/F-559 dated 09/10/2026. Student Tenzin Dolma, "
     "Admission No. HHS-4471, Class XI Science. Annual tuition Rs 30,000; Laboratory Rs 5,000; Books Rs 7,000. "
     "Total Rs 42,000. Bursar (signed)"),
   D("Class 10 marksheet", "MARKSHEET",
     "West Bengal Board of Secondary Education. Marksheet 2026. Tenzin Dolma, Roll 0418-221. Aggregate 88 percent.")],
  env(stated=42000), nmi("Provide proof of admission to class XI."),
  note="Scripted Gemini information request on a complete case.")

S("FE-LC-EDU-05", "LC", "legitimate", "complete", "EDUCATION", "B.Ed fees for Mohan Lal",
  "Mohan Lal teaches children in his village for free and has joined the B.Ed course at Shekhawati Teachers College "
  "to become a qualified teacher. The college fee demand is attached.",
  68000, "Mohan Lal", "SELF", "Jhunjhunu", "Rajasthan", "2026-09-18",
  [D("Fee demand", "FEE_DEMAND",
     "Shekhawati Teachers College, Jhunjhunu. Demand No. STC/B.Ed/26/302 Date 12/09/2026. Student Mohan Lal, Roll BED26-118, "
     "B.Ed Year 1. Tuition Rs 60,000; Practice teaching Rs 5,000; Library Rs 3,000. Total Rs 68,000. Accounts Clerk (signed)"),
   D("Admission letter", "ADMISSION_LETTER",
     "Shekhawati Teachers College. Ref STC/ADM/2026/118 dated 05/09/2026. Mohan Lal is admitted to B.Ed 2026-28. Principal")],
  env(stated=68000), approve())

S("FE-LC-COM-01", "LC", "legitimate", "complete", "COMMUNITY", "Roof repair for the Kallupatti village library",
  "The village library in Kallupatti leaks every monsoon and 3,000 books are at risk. Seva Sangam Trust will replace the "
  "roof. The contractor's quotation and our registration are attached.",
  220000, "Seva Sangam Trust", "ORGANISATION", "Madurai", "Tamil Nadu", "2026-10-21",
  [D("Roofing quotation", "QUOTATION",
     "Meenakshi Roofing Works, Madurai. GSTIN 33AAAAM1111C1Z5. Quotation MRW/Q/2026/144 dated 16/10/2026 for Seva Sangam "
     "Trust: removal of old roof Rs 25,000; steel trusses Rs 95,000; insulated sheets Rs 80,000; labour Rs 20,000. "
     "Total Rs 2,20,000. Proprietor"),
   D("Trust registration", "REGISTRATION",
     "Registration certificate. Seva Sangam Trust registered under the Indian Trusts Act, Reg. No. MDU-IV-77/2016. "
     "Managing trustee: A. Selvaraj")],
  env(stated=220000), approve())

S("FE-LC-COM-02", "LC", "legitimate", "complete", "COMMUNITY", "Hand pumps for three hamlets near Barmer",
  "Three desert hamlets walk 4 km for water. Jal Mitra Society will install three deep hand pumps. The drilling "
  "quotation and our society registration are attached.",
  285000, "Jal Mitra Society", "ORGANISATION", "Barmer", "Rajasthan", "2026-11-09",
  [D("Drilling quotation", "QUOTATION",
     "Thar Drillers, Balotra. GSTIN 08AAAAT2222D1Z9. Quotation TD/2026/087 dated 03/11/2026 for Jal Mitra Society: three "
     "hand pump borings of 300 ft at Rs 95,000 each. Total Rs 2,85,000. Manager"),
   D("Society registration", "REGISTRATION",
     "Registration certificate. Jal Mitra Society registered under the Rajasthan Societies Registration Act, "
     "Reg. No. BMR/SOC/412/2014. Secretary: Gopal Ram")],
  env(stated=285000), approve())

S("FE-LC-COM-03", "LC", "legitimate", "complete", "COMMUNITY", "Flood relief kits for 200 families",
  "Floods in Morigaon district destroyed homes in six villages. Brahmaputra Sahayata Samiti will distribute 200 relief "
  "kits with rice, dal, tarpaulin and a water filter.",
  340000, "Brahmaputra Sahayata Samiti", "ORGANISATION", "Morigaon", "Assam", "2026-09-26",
  [D("Supplier quotation", "QUOTATION",
     "Kamakhya Wholesale Traders, Guwahati. GSTIN 18AAAAK3333E1Z2. Quotation KWT/Q/26/611 dated 23/09/2026 for "
     "Brahmaputra Sahayata Samiti: 200 relief kits at Rs 1,700 each (rice 10 kg, dal 2 kg, tarpaulin, water filter). "
     "Total Rs 3,40,000. Proprietor"),
   D("Samiti registration", "REGISTRATION",
     "Registration certificate. Brahmaputra Sahayata Samiti registered under the Societies Registration Act, "
     "Reg. No. RS/MRG/233/2018. President: Bina Bora")],
  env(stated=340000), approve())

S("FE-LC-COM-04", "LC", "legitimate", "complete", "COMMUNITY", "Wheelchairs for a day-care centre",
  "Sahara Foundation runs a day-care centre for 40 children with cerebral palsy in Lucknow. Twelve children need "
  "proper wheelchairs. The supplier's quotation is attached.",
  132000, "Sahara Foundation", "ORGANISATION", "Lucknow", "Uttar Pradesh", "2026-10-30",
  [D("Wheelchair quotation", "QUOTATION",
     "Avadh Mobility Aids, Aminabad, Lucknow. GSTIN 09AAAAA4444F1Z6. Quotation AMA/26/315 dated 27/10/2026 for Sahara "
     "Foundation: 12 paediatric tilt-in-space wheelchairs at Rs 11,000 each. Total Rs 1,32,000. Sales Manager"),
   D("Foundation registration", "REGISTRATION",
     "Registration certificate. Sahara Foundation registered under section 8 of the Companies Act, CIN "
     "U85300UP2017NPL091122. Director: Nasreen Ahmed")],
  env(stated=132000), approve())

S("FE-LC-COM-05", "LC", "legitimate", "complete", "COMMUNITY", "Solar lights for five anganwadis",
  "Five anganwadi centres near Koraput have no electricity, so children leave before dark. Ujjwal Gram Society will "
  "fit solar lighting kits. The quotation is attached.",
  96000, "Ujjwal Gram Society", "ORGANISATION", "Koraput", "Odisha", "2026-10-03",
  [D("Solar kit quotation", "QUOTATION",
     "Surya Solar Systems, Jeypore. GSTIN 21AAAAS5555G1Z3. Quotation SSS/Q/2026/58 dated 29/09/2026 for Ujjwal Gram "
     "Society: 5 solar lighting kits (panel, battery, 4 lights) at Rs 19,200 each. Total Rs 96,000. Proprietor"),
   D("Society registration", "REGISTRATION",
     "Registration certificate. Ujjwal Gram Society registered under the Societies Registration Act, Reg. No. "
     "KPT/1190/2015. Secretary: Lalita Majhi")],
  env(stated=96000), failure("SERVER_ERROR"), note="Gemini fails (server error).")

# =====================================================================================================================
# LI: legitimate, incomplete (10)
# =====================================================================================================================
S("FE-LI-MED-01", "LI", "legitimate", "incomplete", "MEDICAL", "Spine surgery at the government hospital for Bhola",
  "Bhola Prasad, 39, a construction worker, injured his spine in a fall. The Government Medical College Hospital will "
  "operate free, but he must buy the implants and medicines from the approved shop. The hospital does not give estimates.",
  120000, "Bhola Prasad", "SELF", "Patna", "Bihar", "2026-11-11",
  [D("List of items to purchase", "HOSPITAL_LETTER",
     "Government Medical College Hospital, Patna. Department of Orthopaedics. Patient Bhola Prasad 39 M, Reg. No. "
     "GMCH/ORTH/26/7781. Items to be purchased by the attendant before surgery: pedicle screws 6, rods 2, bone graft "
     "substitute, antibiotics as per list. Date 08/11/2026. Unit In-charge"),
   D("Admission slip", "CLINICAL_NOTE",
     "GMCH Patna. Admitted 07/11/2026. Bhola Prasad 39 M. L1 burst fracture with partial weakness of legs. Planned "
     "posterior fixation. Dr A. K. Singh")],
  env(stated=120000), nmi("A cost estimate or price list for the implants is required."),
  subtype="genuine_but_informal")

S("FE-LI-MED-02", "LI", "legitimate", "incomplete", "MEDICAL", "Dialysis sessions for Lakshmi at a charitable centre",
  "Lakshmi Narayanan, 58, has dialysis twice a week at a charitable centre that charges a fixed amount per session and "
  "gives only payment slips. We ask for three months of sessions.",
  42000, "Lakshmi Narayanan", "SELF", "Coimbatore", "Tamil Nadu", "2026-10-12",
  [D("Payment slips", "RECEIPT",
     "Sri Ramakrishna Charitable Dialysis Centre. Slips for Lakshmi Narayanan: 02/10/2026 Rs 1,750; 06/10/2026 Rs 1,750; "
     "09/10/2026 Rs 1,750."),
   D("Doctor's letter", "CLINICAL_NOTE",
     "Sri Ramakrishna Charitable Dialysis Centre. 10/10/2026. Lakshmi Narayanan 58 F has end-stage kidney disease and needs "
     "haemodialysis twice weekly. Dr M. Krishnan")],
  env(stated=42000), nmi("A formal estimate for the requested sessions is needed."), subtype="genuine_but_informal")

S("FE-LI-EDU-01", "LI", "legitimate", "incomplete", "EDUCATION", "NEET coaching for Asha",
  "Asha Kumari wants to become a doctor. A retired biology teacher in Hazaribagh coaches her for NEET. He charges a "
  "monthly amount and does not issue bills. We ask for ten months of coaching.",
  30000, "Asha Kumari", "SELF", "Hazaribagh", "Jharkhand", "2026-09-29",
  [D("Teacher's letter", "LETTER",
     "To whom it may concern. Asha Kumari attends my NEET biology and chemistry classes six days a week. My fee is Rs 3,000 "
     "per month. B. N. Sinha, retired lecturer, Hazaribagh")],
  env(stated=30000), nmi("Provide an official fee receipt or fee structure."), subtype="genuine_but_informal")

S("FE-LI-COM-01", "LI", "legitimate", "incomplete", "COMMUNITY", "Footbridge rebuilt by villagers in Chamoli",
  "The footbridge to Gwar village washed away. Villagers will rebuild it with their own labour. Materials are bought "
  "locally and the ward member has written the expected cost. There is no formal quotation.",
  75000, "Gwar Gram Vikas Samiti", "ORGANISATION", "Chamoli", "Uttarakhand", "2026-10-06",
  [D("Ward member's note", "LETTER",
     "Gram Panchayat Gwar. The footbridge over the stream was washed away in September. Villagers will rebuild it. "
     "Expected cost of steel cables, planks and cement about Rs 75,000. Ward member, Gwar"),
   D("Samiti registration", "REGISTRATION",
     "Registration certificate. Gwar Gram Vikas Samiti registered under the Societies Registration Act, Reg. No. "
     "CHM/SOC/88/2019. President: Puran Singh")],
  env(stated=75000), nmi("A supplier quotation for the materials is required."), subtype="genuine_but_informal")

S("FE-LI-COM-02", "LI", "legitimate", "incomplete", "COMMUNITY", "Community kitchen after the cyclone",
  "After the cyclone, 90 families in Gopalpur fishing village have no way to cook. Volunteers of Sagar Sathi Trust will "
  "run a community kitchen for one month, buying rice and vegetables daily from local sellers.",
  60000, "Sagar Sathi Trust", "ORGANISATION", "Ganjam", "Odisha", "2026-11-03",
  [D("Kitchen plan", "PLAN",
     "Sagar Sathi Trust. Community kitchen at Gopalpur for 30 days. Rice, dal, vegetables and fuel bought daily from "
     "local sellers, about Rs 2,000 per day. Coordinator: S. Behera"),
   D("Trust registration", "REGISTRATION",
     "Registration certificate. Sagar Sathi Trust registered under the Indian Trusts Act, Reg. No. GJM-IV-19/2020. "
     "Managing trustee: S. Behera")],
  env(stated=60000), approve(), subtype="genuine_but_informal", note="Gemini scripted to miss the missing quotation.")

S("FE-LI-MED-03", "LI", "legitimate", "incomplete", "MEDICAL", "Knee surgery for Shanti",
  "Shanti Devi, 57, has severe arthritis in her right knee and cannot work in the fields. The doctor has advised a knee "
  "replacement. We are still waiting for the hospital estimate.",
  210000, "Shanti Devi", "SELF", "Meerut", "Uttar Pradesh", "2026-10-24",
  [D("Orthopaedic note", "CLINICAL_NOTE",
     "Meerut Joint Care Hospital OPD 20/10/2026. Shanti Devi 57 F. Grade IV osteoarthritis right knee. Advised right total "
     "knee replacement. Dr N. Tyagi MS Ortho")],
  env(stated=210000), nmi("The hospital estimate is missing."), subtype="no_cost_document")

S("FE-LI-EDU-02", "LI", "legitimate", "incomplete", "EDUCATION", "Engineering admission for Imran",
  "Imran Sheikh got admission to B.Tech Civil at Marathwada Engineering College through the state counselling. We are "
  "raising the first-year fees. The college will give the fee demand after reporting.",
  85000, "Imran Sheikh", "SELF", "Aurangabad", "Maharashtra", "2026-09-16",
  [D("Allotment letter", "ADMISSION_LETTER",
     "State CET Cell. Allotment letter ACAP-2026-55120 dated 10/09/2026. Imran Sheikh is allotted B.Tech Civil at "
     "Marathwada Engineering College, Aurangabad. Report by 25/09/2026.")],
  env(stated=85000), approve(), subtype="no_cost_document", note="Gemini scripted to miss the missing fee demand.")

S("FE-LI-EDU-03", "LI", "legitimate", "incomplete", "EDUCATION", "Diploma fees for Kavya",
  "Kavya Shetty is in the final year of a diploma in computer engineering. We attach the fee structure we have. The "
  "college has not yet issued this year's demand.",
  52000, "Kavya Shetty", "SELF", "Mangaluru", "Karnataka", "2026-10-20",
  [D("Fee structure", "FEE_STRUCTURE",
     "Karavali Polytechnic, Mangaluru. Fee structure 2024-25, issued 10/06/2024. Diploma in Computer Engineering: tuition "
     "Rs 45,000; examination Rs 4,000; laboratory Rs 3,000 per year. Total Rs 52,000. Office Superintendent"),
   D("Bonafide certificate", "CERTIFICATE",
     "Karavali Polytechnic. Bonafide certificate. Kavya Shetty, Reg. No. KP23CS041, is a student of Diploma in Computer "
     "Engineering, final year 2026-27. Principal")],
  env(stated=52000), failure("truncated"), subtype="unacceptable_cost_document",
  note="Fee structure is more than a year old. Gemini fails (truncated response).")

S("FE-LI-COM-03", "LI", "legitimate", "incomplete", "COMMUNITY", "Toilets for Bhimnagar school",
  "The girls' toilets at Bhimnagar government school are broken and many girls stay home. Shiksha Sahyog Manch will "
  "repair them. A mason has told us the approximate cost.",
  140000, "Shiksha Sahyog Manch", "ORGANISATION", "Nanded", "Maharashtra", "2026-11-07",
  [D("Approximate cost", "ESTIMATE",
     "Approximate cost for repairing school toilets: tiles, doors, plumbing and water tank, about Rs 1,40,000."),
   D("Manch registration", "REGISTRATION",
     "Registration certificate. Shiksha Sahyog Manch registered under the Societies Registration Act, Reg. No. "
     "NND/SOC/301/2017. Secretary: R. Kamble")],
  env(stated=140000), nmi("The cost document has no issuer, date or reference."), subtype="unacceptable_cost_document")

S("FE-LI-MED-04", "LI", "legitimate", "incomplete", "MEDICAL", "Hernia operation for Joseph",
  "Joseph Mathew, 49, works as a loader and has a painful hernia that stops him working. We attach the hospital estimate. "
  "The doctor's report will follow.",
  48000, "Joseph Mathew", "SELF", "Thrissur", "Kerala", "2026-10-02",
  [D("Hospital estimate", "HOSPITAL_ESTIMATE",
     "Amala Mission Hospital, Thrissur. Estimate AMH/26/3390 dated 28/09/2026. Patient Joseph Mathew 49 M. Laparoscopic "
     "hernia repair with mesh. Package Rs 48,000. Billing Officer (signed)")],
  env(stated=48000), nmi("A doctor's diagnosis or recommendation is required."), subtype="missing_identity_or_need",
  note="No medical document showing the need.")

# =====================================================================================================================
# FD: fraud detectable from the documents (15)
# =====================================================================================================================
S("FE-FD-MED-01", "FD", "fraudulent", "complete", "MEDICAL", "Bypass surgery for Suresh",
  "Suresh Yadav, 61, needs urgent heart bypass surgery at Jeevan Rekha Heart Institute. The total cost is Rs 4,50,000. "
  "Please help before it is too late.",
  450000, "Suresh Yadav", "SELF", "Indore", "Madhya Pradesh", "2026-10-26",
  [D("Cardiac estimate", "HOSPITAL_ESTIMATE",
     "Jeevan Rekha Heart Institute, Vijay Nagar, Indore. Estimate JRHI/E/26/882 dated 21/10/2026. Patient Suresh Yadav 61 M, "
     "UHID JR-41207. CABG package Rs 1,80,000. Total estimate Rs 1,80,000. Billing Manager (signed)"),
   D("Cardiology note", "CLINICAL_NOTE",
     "Jeevan Rekha Heart Institute. 19/10/2026. Suresh Yadav 61 M. Triple vessel disease on angiography. Advised CABG. "
     "Dr R. Jain DM Cardiology")],
  env(issuer="CONFIRMED", stated=180000), flag("CONTRADICTION",
     "The goal of Rs 4,50,000 is far above the hospital estimate.", "Cardiac estimate", "Total estimate Rs 1,80,000"),
  mechanism="amount_inflation")

S("FE-FD-MED-02", "FD", "fraudulent", "complete", "MEDICAL", "Brain tumour surgery for Mukesh",
  "My brother Mukesh Sharma, 42, has a brain tumour and needs surgery at Neuro Care Hospital. The estimate is attached.",
  320000, "Mukesh Sharma", "SELF", "Jaipur", "Rajasthan", "2026-11-01",
  [D("Neurosurgery estimate", "HOSPITAL_ESTIMATE",
     "Neuro Care Hospital, Malviya Nagar, Jaipur. Estimate NCH/26/5512 dated 27/10/2026. Patient Rakesh Verma 47 M, UHID "
     "NCH-60331. Craniotomy and excision of tumour. Total estimate Rs 3,20,000. Billing Manager (signed)"),
   D("MRI report", "REPORT",
     "Neuro Care Hospital Imaging. 25/10/2026. Patient Rakesh Verma 47 M. Left frontal meningioma 4 cm. Dr S. Mathur")],
  env(ben="CONTRADICTED", inst="CONTRADICTED", stated=320000, note="Documents belong to another patient."),
  approve(), mechanism="document_contradiction", note="Gemini scripted to miss the different patient name.")

S("FE-FD-MED-03", "FD", "fraudulent", "complete", "MEDICAL", "Hospital bill for Anita's delivery complications",
  "Anita Gupta had a difficult delivery and her baby was in the NICU for two weeks. We cannot pay the hospital bill of "
  "Rs 2,10,000. Please help us take the baby home.",
  210000, "Anita Gupta", "SELF", "Kanpur", "Uttar Pradesh", "2026-10-17",
  [D("Final bill", "HOSPITAL_BILL",
     "Matri Shishu Hospital, Kanpur. Final bill MSH/IPD/26/2290 dated 12/10/2026. Patient Anita Gupta 29 F, IP No. "
     "MSH-IP-7711. Delivery and NICU 14 days. Total Rs 2,10,000. Amount received Rs 2,10,000. Balance nil. Paid in full. "
     "Cashier (signed)"),
   D("Discharge summary", "DISCHARGE_SUMMARY",
     "Matri Shishu Hospital. Discharge summary. Anita Gupta 29 F, IP No. MSH-IP-7711. Admitted 27/09/2026, discharged "
     "11/10/2026 with baby. Dr K. Awasthi")],
  env(issuer="CONFIRMED", stated=210000, other=210000, note="The bill was paid in full before the campaign."),
  flag("SUSPECTED_FRAUD", "The final bill shows it was already paid in full.", "Final bill", "Balance nil. Paid in full."),
  mechanism="independent_record_contradiction")

S("FE-FD-MED-04", "FD", "fraudulent", "complete", "MEDICAL", "Appendix surgery bill for Rohit",
  "Rohit Saini, 23, had emergency appendix surgery last week. The bill is attached and we need help to pay it.",
  95000, "Rohit Saini", "SELF", "Ambala", "Haryana", "2026-10-09",
  [D("Hospital bill", "HOSPITAL_BILL",
     "Shivalik Surgical Hospital, Ambala Cantt. Bill SSH/26/9918 dated 28/10/2026. Patient Rohit Saini 23 M, IP No. SSH-4410. "
     "Laparoscopic appendicectomy, surgery performed on 26/10/2026. Total Rs 95,000. Cashier (signed)"),
   D("Discharge card", "DISCHARGE_SUMMARY",
     "Shivalik Surgical Hospital. Discharge card. Rohit Saini 23 M, IP No. SSH-4410. Acute appendicitis. Discharged in "
     "stable condition. Dr P. Malhotra")],
  env(inst="CONTRADICTED", stated=None, issuer="CONTRADICTED", note="No such admission on the hospital's records."),
  flag_unquoted("The bill appears to be fabricated."), mechanism="document_contradiction",
  note="Bill and surgery dated after the submission date.")

S("FE-FD-MED-05", "FD", "fraudulent", "complete", "MEDICAL", "Funeral and hospital dues for Harish",
  "Harish Chandra died in the ICU at Lifeline Hospital on 14/09/2026 after a stroke. His family cannot pay the hospital "
  "dues of Rs 1,40,000.",
  140000, "Harish Chandra", "SELF", "Dehradun", "Uttarakhand", "2026-09-28",
  [D("Death certificate", "CERTIFICATE",
     "Municipal Corporation Dehradun. Death certificate. Name Harish Chandra, male, age 64. Date of death 02/09/2026. "
     "Place of death: residence. Registrar of Births and Deaths"),
   D("Hospital dues statement", "HOSPITAL_BILL",
     "Lifeline Hospital, Dehradun. Statement LH/26/4471 dated 20/09/2026. Patient Harish Chandra 64 M. ICU 6 days, died on "
     "14/09/2026. Outstanding Rs 1,40,000. Accounts Officer (signed)")],
  env(inst="CONTRADICTED", issuer="CONTRADICTED", stated=None), nmi("Provide the ICU case summary."),
  mechanism="document_contradiction")

S("FE-FD-MED-06", "FD", "fraudulent", "complete", "MEDICAL", "Spine surgery for Geeta",
  "Geeta Rawat, 50, needs spine surgery for a slipped disc at Orthocare Hospital. Without surgery she cannot walk. "
  "The estimate is attached.",
  260000, "Geeta Rawat", "SELF", "Haldwani", "Uttarakhand", "2026-11-06",
  [D("Surgery estimate", "HOSPITAL_ESTIMATE",
     "Orthocare Hospital, Haldwani. Estimate OCH/26/1207 dated 02/11/2026. Patient Geeta Rawat 50 F, UHID OCH-22871. "
     "Lumbar discectomy and fixation. Total estimate Rs 2,60,000. Billing Manager (signed)"),
   D("Spine clinic note", "CLINICAL_NOTE",
     "Orthocare Hospital Spine Clinic 31/10/2026. Geeta Rawat 50 F. L4-L5 disc bulge with mild back pain, no weakness. "
     "No surgery is indicated at present. Advised physiotherapy for six weeks. Dr M. Bisht")],
  env(inst="CONTRADICTED", stated=260000, note="The hospital says surgery was not advised."),
  flag("CONTRADICTION", "The clinic note says surgery is not indicated.", "Spine clinic note",
       "No surgery is indicated at present"), mechanism="misrepresented_need")

S("FE-FD-EDU-01", "FD", "fraudulent", "complete", "EDUCATION", "Medical college fees for Neha",
  "Neha Kapoor got into MBBS at Shri Balaji Medical College. Her first-year fee is due. Please transfer to the account "
  "given below so we can pay the college on time.",
  450000, "Neha Kapoor", "SELF", "Bhopal", "Madhya Pradesh", "2026-09-24",
  [D("Fee demand", "FEE_DEMAND",
     "Shri Balaji Medical College, Bhopal. Accounts. Demand SBMC/MBBS/26/118 dated 19/09/2026. Student Neha Kapoor, "
     "MBBS Year 1. Tuition Rs 4,50,000. Total Rs 4,50,000. Accounts Officer (signed)"),
   D("Payout details", "BANK_DETAILS",
     "Account holder: Rahul Mehta. Bank: Bhopal Urban Co-operative Bank. Account No. 004512003377. Funds for the college "
     "fee may be sent here.")],
  env(pay="CONTRADICTED", stated=450000, note="The account belongs to an unrelated agent."),
  flag("SUSPECTED_FRAUD", "The payout account belongs to a different person, not the college or the student.",
       "Payout details", "Account holder: Rahul Mehta"), mechanism="suspicious_payee")

S("FE-FD-EDU-02", "FD", "fraudulent", "complete", "EDUCATION", "Hostel and college fees for Vikram",
  "Vikram Chauhan is in second-year B.Com. His total fees for the year including hostel come to Rs 2,40,000.",
  240000, "Vikram Chauhan", "SELF", "Shimla", "Himachal Pradesh", "2026-10-13",
  [D("College fee demand", "FEE_DEMAND",
     "Himgiri Commerce College, Shimla. Demand HCC/26/773 dated 08/10/2026. Student Vikram Chauhan, Roll BCOM25-210, "
     "B.Com Year 2. Tuition Rs 55,000; Hostel Rs 30,000. Total Rs 85,000. Accounts Clerk (signed)"),
   D("Identity card", "IDENTITY", "Himgiri Commerce College identity card. Vikram Chauhan, B.Com, Roll BCOM25-210.")],
  env(stated=85000), approve(), mechanism="amount_inflation", note="Gemini scripted to miss the inflation.")

S("FE-FD-EDU-03", "FD", "fraudulent", "complete", "EDUCATION", "Engineering fees for Divya",
  "Divya Pillai is in third-year engineering and her fee of Rs 1,30,000 is unpaid. Please help her continue.",
  130000, "Divya Pillai", "SELF", "Kollam", "Kerala", "2026-11-10",
  [D("Fee demand", "FEE_DEMAND",
     "TKM Institute of Technology, Kollam. Demand TKMIT/26/2201 dated 03/11/2026. Student Divya Pillai, Roll 24CS112, "
     "B.Tech Year 3. Tuition Rs 1,30,000. Total Rs 1,30,000. Accounts Officer (signed)"),
   D("Scholarship sanction", "LETTER",
     "Kerala State Merit Scholarship Cell. Sanction KSMS/2026/8812 dated 05/11/2026. Divya Pillai, TKMIT, B.Tech Year 3: "
     "full tuition fee of Rs 1,30,000 for 2026-27 sanctioned and paid directly to the institution. Joint Director")],
  env(stated=130000, other=130000), approve(), mechanism="amount_inflation",
  note="Scholarship already pays the full fee. Gemini scripted to miss it.")

S("FE-FD-EDU-04", "FD", "fraudulent", "complete", "EDUCATION", "Pharmacy course fees for Sneha",
  "Sneha Joshi is in the first year of B.Pharm. The college fee demand and her identity card are attached.",
  92000, "Sneha Joshi", "SELF", "Nashik", "Maharashtra", "2026-10-05",
  [D("Fee demand", "FEE_DEMAND",
     "Godavari College of Pharmacy, Nashik. Demand GCP/26/415 dated 30/09/2026. Student Sneha Joshi, Roll BP26-071, "
     "B.Pharm Year 1. Total Rs 92,000. Accounts Officer (signed)"),
   D("Identity card", "IDENTITY",
     "Godavari College of Pharmacy identity card. Sneha Joshi, B.Pharm, Roll BP26-118, valid till 2030.")],
  env(ben="CONTRADICTED", inst="CONTRADICTED", stated=None, issuer="CONTRADICTED",
      note="Roll BP26-071 belongs to another student."),
  flag("CONTRADICTION", "The roll number on the fee demand differs from the identity card.", "Identity card",
       "Roll BP26-118"), mechanism="document_contradiction")

S("FE-FD-EDU-05", "FD", "fraudulent", "complete", "EDUCATION", "Final-year fees for Arvind",
  "Arvind Desai is in the final year of B.Tech at Sardar Patel Institute of Technology. The fee demand and the college's "
  "letter with its bank details are attached.",
  115000, "Arvind Desai", "SELF", "Vadodara", "Gujarat", "2026-10-22",
  [D("Fee demand", "FEE_DEMAND",
     "Sardar Patel Institute of Technology, Vadodara. Demand SPIT/26/3310 dated 16/10/2026. Student Arvind Desai, Roll "
     "22ME045, B.Tech Year 4. Total Rs 1,15,000. Pay by NEFT to Account name: Sardar Patel Institute of Technology, A/c No. "
     "30418877201, IFSC SBIN0004120. Accounts Officer (signed)"),
   D("College letter for donors", "LETTER",
     "Sardar Patel Institute of Technology. To donors supporting Arvind Desai: please transfer the fee to Account name: "
     "Sardar Patel Institute of Technology A/c No. 50100234998812, HDFC Bank. Accounts Section")],
  env(pay="CONTRADICTED", stated=115000, note="The second account belongs to a private individual."),
  approve(), mechanism="suspicious_payee", note="Bank details substituted in the second letter. Gemini misses it.")

S("FE-FD-COM-01", "FD", "fraudulent", "complete", "COMMUNITY", "Classrooms for Ramgarh school",
  "Navjyoti Trust is building two classrooms at Ramgarh government school. The total project cost is Rs 9,00,000.",
  900000, "Navjyoti Trust", "ORGANISATION", "Alwar", "Rajasthan", "2026-09-21",
  [D("Contractor quotation", "QUOTATION",
     "Mewat Builders, Alwar. GSTIN 08AAAAM6666H1Z1. Quotation MB/Q/26/091 dated 15/09/2026 for Navjyoti Trust: two "
     "classrooms with verandah, 600 sq ft. Total Rs 3,10,000. Proprietor"),
   D("Trust registration", "REGISTRATION",
     "Registration certificate. Navjyoti Trust registered under the Indian Trusts Act, Reg. No. ALW-IV-51/2012. "
     "Managing trustee: D. Meena")],
  env(stated=310000), flag("CONTRADICTION", "The goal is almost three times the contractor's quotation.",
                           "Contractor quotation", "Total Rs 3,10,000"), mechanism="amount_inflation")

S("FE-FD-COM-02", "FD", "fraudulent", "complete", "COMMUNITY", "Community hall roof for Pipra",
  "Gram Utthan Samiti needs funds to re-roof the community hall in Pipra village before the winter. The supplier's "
  "quotation is attached.",
  180000, "Gram Utthan Samiti", "ORGANISATION", "Gorakhpur", "Uttar Pradesh", "2026-10-29",
  [D("Roofing quotation", "QUOTATION",
     "Purvanchal Steel and Sheets, Gorakhpur. Quotation PSS/26/402 dated 20/10/2026 for Gram Utthan Samiti: community hall "
     "roof, 1,800 sq ft. Total Rs 1,80,000. Manager"),
   D("Work completion certificate", "CERTIFICATE",
     "Gram Panchayat Pipra. Certificate dated 25/10/2026: the community hall roof has been completed by Purvanchal Steel "
     "and Sheets and the full payment of Rs 1,80,000 has been made from the panchayat fund. Pradhan, Pipra")],
  env(stated=180000, other=180000, note="Work completed and paid from public funds."),
  flag("SUSPECTED_FRAUD", "The work is certified as completed and fully paid.", "Work completion certificate",
       "the full payment of Rs 1,80,000 has been made from the panchayat fund"), mechanism="independent_record_contradiction")

S("FE-FD-COM-03", "FD", "fraudulent", "complete", "COMMUNITY", "Drinking water plant for Kheda villages",
  "Jan Seva Trust will install an RO drinking water plant for four villages in Kheda. Our registration and the plant "
  "quotation are attached.",
  360000, "Jan Seva Trust", "ORGANISATION", "Kheda", "Gujarat", "2026-11-04",
  [D("RO plant quotation", "QUOTATION",
     "Aqua Pure Systems, Nadiad. GSTIN 24AAAAA7777J1Z4. Quotation APS/26/211 dated 30/10/2026 for Jan Seva Trust: 1,000 "
     "litre per hour RO plant with installation. Total Rs 3,60,000. Sales Manager"),
   D("Registration certificate", "REGISTRATION",
     "Registration certificate. Gram Vikas Samiti, Anand, registered under the Societies Registration Act, Reg. No. "
     "GUJ/ANAND/5541/2011. President: H. Patel")],
  env(ben="CONTRADICTED", inst="CONTRADICTED", stated=360000, note="The registration belongs to a different organisation."),
  flag_unquoted("The registration may not match the campaigning organisation."), mechanism="document_contradiction")

S("FE-FD-COM-04", "FD", "fraudulent", "complete", "COMMUNITY", "Sewing machines for a women's group",
  "Nari Shakti Mahila Mandal will buy 25 sewing machines so women in Sangli can earn from tailoring. The supplier's "
  "quotation and its bank mandate are attached.",
  162500, "Nari Shakti Mahila Mandal", "ORGANISATION", "Sangli", "Maharashtra", "2026-10-10",
  [D("Supplier quotation", "QUOTATION",
     "Shree Ganesh Traders, Sangli. GSTIN 27AAAAS8888K1Z7. Quotation SGT/26/144 dated 06/10/2026 for Nari Shakti Mahila "
     "Mandal: 25 sewing machines at Rs 6,500 each. Total Rs 1,62,500. Payable to: Shree Ganesh Traders, Account No: "
     "918020044556677. Proprietor"),
   D("Supplier bank mandate", "BANK_DETAILS",
     "Bank mandate. Account holder: Shree Ganesh Traders, Account No: 33445566778, Sangli Urban Bank. Authorised signatory"),
   D("Mandal registration", "REGISTRATION",
     "Registration certificate. Nari Shakti Mahila Mandal registered under the Societies Registration Act, Reg. No. "
     "SNG/SOC/77/2016. President: Sunita Jadhav")],
  env(pay="CONTRADICTED", stated=162500, note="The mandate account is not the supplier's."),
  failure("invalid_json"), mechanism="suspicious_payee", note="Gemini returns invalid JSON.")

# =====================================================================================================================
# FS: sophisticated, internally consistent fraud (10)
# =====================================================================================================================
S("FE-FS-MED-01", "FS", "fraudulent", "complete", "MEDICAL", "Liver transplant for Pradeep",
  "Pradeep Saxena, 48, has liver failure and needs a transplant at Sanjeevani Liver Institute. His wife is the donor. "
  "The estimate and the hepatologist's note are attached.",
  1800000, "Pradeep Saxena", "SELF", "Gurugram", "Haryana", "2026-10-14",
  [D("Transplant estimate", "HOSPITAL_ESTIMATE",
     "Sanjeevani Liver Institute, Sector 44, Gurugram. Estimate SLI/TX/26/0912 dated 10/10/2026. Patient Pradeep Saxena "
     "48 M, UHID SLI-77310. Living donor liver transplant package Rs 18,00,000. Total estimate Rs 18,00,000. Transplant "
     "Coordinator (signed)"),
   D("Hepatology note", "CLINICAL_NOTE",
     "Sanjeevani Liver Institute. 08/10/2026. Pradeep Saxena 48 M, UHID SLI-77310. Decompensated cirrhosis, MELD 24. "
     "Listed for living donor liver transplant. Dr A. Kohli DM Hepatology")],
  env(inst="CONTRADICTED", issuer="CONTRADICTED", stated=None, note="The hospital has no such patient."),
  approve(), mechanism="consistent_fabrication")

S("FE-FS-MED-02", "FS", "fraudulent", "complete", "MEDICAL", "Knee replacements for Usha",
  "Usha Menon, 63, needs both knees replaced at Lakeshore Orthopaedic Centre. The estimate and the surgeon's advice "
  "are attached.",
  300000, "Usha Menon", "SELF", "Kochi", "Kerala", "2026-10-27",
  [D("Surgery estimate", "HOSPITAL_ESTIMATE",
     "Lakeshore Orthopaedic Centre, Kochi. Estimate LOC/26/2240 dated 22/10/2026. Patient Usha Menon 63 F, UHID LOC-50177. "
     "Bilateral total knee replacement. Total estimate Rs 3,00,000. Billing Manager (signed)"),
   D("Surgeon's advice", "CLINICAL_NOTE",
     "Lakeshore Orthopaedic Centre 20/10/2026. Usha Menon 63 F. Bilateral grade IV osteoarthritis. Advised bilateral TKR. "
     "Dr J. Varghese MS Ortho")],
  env(stated=120000, note="The billing desk's own estimate is Rs 1,20,000; the uploaded estimate was edited."),
  approve(), mechanism="amount_inflation", note="Consistent edited estimate; only the cost issuer reveals it.")

S("FE-FS-MED-03", "FS", "fraudulent", "complete", "MEDICAL", "Heart valve surgery for Bhagwan Das",
  "Bhagwan Das, 58, needs a heart valve replacement at Narmada Heart Hospital. The estimate is attached and we have no "
  "other help.",
  250000, "Bhagwan Das", "SELF", "Jabalpur", "Madhya Pradesh", "2026-09-23",
  [D("Cardiac surgery estimate", "HOSPITAL_ESTIMATE",
     "Narmada Heart Hospital, Jabalpur. Estimate NHH/26/6612 dated 18/09/2026. Patient Bhagwan Das 58 M, UHID NHH-30922. "
     "Mitral valve replacement. Total estimate Rs 2,50,000. Billing Manager (signed)"),
   D("Echo report", "REPORT",
     "Narmada Heart Hospital. Echo 16/09/2026. Bhagwan Das 58 M. Severe rheumatic mitral stenosis. Valve area 0.8 sq cm. "
     "Dr P. Tiwari")],
  env(stated=250000, other=200000, note="Ayushman Bharat already covers Rs 2,00,000 of the package."),
  flag_unquoted("Such surgery is usually covered by government insurance."), mechanism="amount_inflation",
  note="Undisclosed insurance; only the cost issuer reveals it.")

S("FE-FS-MED-04", "FS", "fraudulent", "complete", "MEDICAL", "Leukaemia treatment for little Aarav",
  "Aarav Bansal, 7, has leukaemia and is being treated at City Children's Cancer Hospital. The hospital's estimate and "
  "the doctor's note are attached. You can call the hospital helpdesk on 98110 44321 to confirm.",
  600000, "Aarav Bansal", "SELF", "Ghaziabad", "Uttar Pradesh", "2026-11-08",
  [D("Treatment estimate", "HOSPITAL_ESTIMATE",
     "City Children's Cancer Hospital, Ghaziabad. Helpdesk 98110 44321. Estimate CCCH/26/417 dated 04/11/2026. Patient "
     "Aarav Bansal 7 M, UHID CCCH-1288. ALL induction and consolidation chemotherapy. Total estimate Rs 6,00,000. "
     "Billing Manager (signed)"),
   D("Oncologist note", "CLINICAL_NOTE",
     "City Children's Cancer Hospital. 02/11/2026. Aarav Bansal 7 M. B-cell acute lymphoblastic leukaemia. Started on "
     "induction chemotherapy. Dr N. Arora DM Paediatric Oncology")],
  env(inst="UNREACHABLE", issuer="UNREACHABLE", stated=None,
      supplied={"INSTITUTION": "CONFIRMED", "BENEFICIARY": "CONFIRMED"},
      note="The 'helpdesk' number is a confederate; the hospital is not in any directory."),
  approve(), mechanism="consistent_fabrication", note="Campaign-supplied confederate confirms; independent channel finds nothing.")

S("FE-FS-EDU-01", "FS", "fraudulent", "complete", "EDUCATION", "Law school fees for Karan",
  "Karan Malhotra has been admitted to the five-year law course at National Law Academy, Chandigarh. The admission "
  "letter and fee demand are attached.",
  210000, "Karan Malhotra", "SELF", "Chandigarh", "Chandigarh", "2026-09-17",
  [D("Admission letter", "ADMISSION_LETTER",
     "National Law Academy, Chandigarh. Ref NLA/ADM/26/331 dated 08/09/2026. Karan Malhotra is admitted to BA LLB (Hons) "
     "2026-31. Registrar"),
   D("Fee demand", "FEE_DEMAND",
     "National Law Academy, Chandigarh. Demand NLA/F/26/331 dated 10/09/2026. Student Karan Malhotra, BA LLB Year 1. "
     "Tuition Rs 1,80,000; Hostel Rs 30,000. Total Rs 2,10,000. Finance Officer (signed)")],
  env(inst="CONTRADICTED", issuer="CONTRADICTED", stated=None, note="The academy has no such admission."),
  approve(), mechanism="consistent_fabrication")

S("FE-FS-EDU-02", "FS", "fraudulent", "complete", "EDUCATION", "Hotel management fees for Riya",
  "Riya Fernandes is in the second year of hotel management at Konkan Institute of Hospitality. The fee demand is "
  "attached.",
  160000, "Riya Fernandes", "SELF", "Margao", "Goa", "2026-10-07",
  [D("Fee demand", "FEE_DEMAND",
     "Konkan Institute of Hospitality, Margao. Demand KIH/26/877 dated 01/10/2026. Student Riya Fernandes, Roll HM25-033, "
     "BHM Year 2. Tuition Rs 1,40,000; Kitchen practicals Rs 20,000. Total Rs 1,60,000. Accounts Officer (signed)"),
   D("Identity card", "IDENTITY", "Konkan Institute of Hospitality identity card. Riya Fernandes, BHM, Roll HM25-033.")],
  env(stated=60000, note="The accounts office states the fee due is Rs 60,000."),
  approve(), mechanism="amount_inflation", note="Consistent edited fee demand.")

S("FE-FS-EDU-03", "FS", "fraudulent", "complete", "EDUCATION", "Architecture fees for Farhan",
  "Farhan Ali is in the third year of B.Arch at Deccan School of Architecture. Please help with this year's fees.",
  175000, "Farhan Ali", "SELF", "Hyderabad", "Telangana", "2026-10-18",
  [D("Fee demand", "FEE_DEMAND",
     "Deccan School of Architecture, Hyderabad. Demand DSA/26/1180 dated 12/10/2026. Student Farhan Ali, Roll ARC24-019, "
     "B.Arch Year 3. Total Rs 1,75,000. Accounts Officer (signed)"),
   D("Bonafide certificate", "CERTIFICATE",
     "Deccan School of Architecture. Bonafide certificate. Farhan Ali, Roll ARC24-019, B.Arch 2024-29. Registrar")],
  env(pay="CONTRADICTED", stated=175000, note="The payout account registered with the platform belongs to a third party."),
  failure("READ_TIMEOUT"), mechanism="suspicious_payee", note="Payout account diverted; Gemini times out.")

S("FE-FS-COM-01", "FS", "fraudulent", "complete", "COMMUNITY", "Eye camp for 500 elderly villagers",
  "Drishti Seva Sansthan will hold a free eye camp with 150 cataract operations in Sikar district. Our registration and "
  "the hospital's quotation are attached.",
  450000, "Drishti Seva Sansthan", "ORGANISATION", "Sikar", "Rajasthan", "2026-11-12",
  [D("Hospital quotation", "QUOTATION",
     "Shekhawati Eye Hospital, Sikar. Quotation SEH/26/88 dated 06/11/2026 for Drishti Seva Sansthan: 150 cataract "
     "operations at Rs 3,000 each. Total Rs 4,50,000. Administrator"),
   D("Sansthan registration", "REGISTRATION",
     "Registration certificate. Drishti Seva Sansthan registered under the Rajasthan Societies Registration Act, Reg. No. "
     "SKR/SOC/902/2013. Secretary: M. Saini")],
  env(ben="CONTRADICTED", inst="CONTRADICTED", stated=None, issuer="UNREACHABLE",
      note="No such registration exists in the state registry."),
  nmi("Provide the camp permission from the district health officer."), mechanism="consistent_fabrication")

S("FE-FS-COM-02", "FS", "fraudulent", "complete", "COMMUNITY", "Science lab for Kalahandi high school",
  "Vidya Vikas Trust will equip the science laboratory at a high school in Kalahandi. The supplier's quotation is "
  "attached.",
  280000, "Vidya Vikas Trust", "ORGANISATION", "Bhawanipatna", "Odisha", "2026-10-01",
  [D("Lab equipment quotation", "QUOTATION",
     "Utkal Scientific Suppliers, Bhubaneswar. GSTIN 21AAAAU9999L1Z8. Quotation USS/26/301 dated 26/09/2026 for Vidya "
     "Vikas Trust: physics, chemistry and biology lab sets. Total Rs 2,80,000. Sales Manager"),
   D("Trust registration", "REGISTRATION",
     "Registration certificate. Vidya Vikas Trust registered under the Indian Trusts Act, Reg. No. KLH-IV-14/2018. "
     "Managing trustee: B. Naik")],
  env(stated=95000, note="The supplier's own quotation was Rs 95,000."), approve(), mechanism="amount_inflation")

S("FE-FS-COM-03", "FS", "fraudulent", "complete", "COMMUNITY", "Ambulance for Mandla tribal villages",
  "Van Jan Kalyan Samiti will buy an ambulance for 30 tribal villages near Mandla. The dealer's quotation and our "
  "registration are attached.",
  1250000, "Van Jan Kalyan Samiti", "ORGANISATION", "Mandla", "Madhya Pradesh", "2026-10-23",
  [D("Ambulance quotation", "QUOTATION",
     "Mahakaushal Motors, Jabalpur. GSTIN 23AAAAM1212M1Z2. Quotation MM/26/56 dated 19/10/2026 for Van Jan Kalyan Samiti: "
     "Type B ambulance with fitting. Total Rs 12,50,000. Sales Manager"),
   D("Samiti registration", "REGISTRATION",
     "Registration certificate. Van Jan Kalyan Samiti registered under the MP Societies Registration Act, Reg. No. "
     "MDL/SOC/45/2010. President: R. Dhurve")],
  env(stated=1250000, note="Collusive: the dealer confirms an inflated price and returns a kickback; every party "
                            "contacted confirms."),
  approve(), mechanism="consistent_fabrication", note="Collusive insider fraud that no independent party reveals.")

# =====================================================================================================================
# BC: borderline or contradictory (10)
# =====================================================================================================================
S("FE-BC-MED-01", "BC", "borderline", "complete", "MEDICAL", "Second admission for Kiran's infection",
  "Kiran Bhatt, 36, was readmitted with an infection after her surgery. The hospital estimate for the second admission "
  "is attached.",
  90000, "Kiran Bhatt", "SELF", "Rajkot", "Gujarat", "2026-10-25",
  [D("Estimate", "HOSPITAL_ESTIMATE",
     "Saurashtra Hospital, Rajkot. Estimate SRH/26/3002 dated 21/10/2026. Patient Kiran Bhatt 36 F, UHID SRH-11980. "
     "Readmission for wound infection, IV antibiotics 7 days. Total estimate Rs 90,000. Billing Manager (signed)"),
   D("Discharge summary (first admission)", "DISCHARGE_SUMMARY",
     "Saurashtra Hospital. Discharge summary. Kiran Bhatt 38 F, UHID SRH-11980. Admitted 02/10/2026, discharged "
     "09/10/2026 after laparoscopic cholecystectomy. Dr T. Joshi")],
  env(stated=90000), flag("CONTRADICTION", "The patient's age differs between documents (36 and 38).",
                          "Discharge summary (first admission)", "Kiran Bhatt 38 F"),
  note="Age differs by two years: clerical or a different person.")

S("FE-BC-MED-02", "BC", "borderline", "complete", "MEDICAL", "Cancer surgery after transfer for Abdul",
  "Abdul Rehman, 55, was diagnosed with oral cancer at the district hospital and has been referred to Coastal Cancer "
  "Centre for surgery. The estimate is attached.",
  280000, "Abdul Rehman", "SELF", "Udupi", "Karnataka", "2026-09-19",
  [D("Referral letter", "LETTER",
     "District Hospital Udupi. 10/09/2026. Abdul Rehman 55 M. Carcinoma of the left buccal mucosa on biopsy. Referred to a "
     "higher centre for surgery. Medical Officer"),
   D("Surgery estimate", "HOSPITAL_ESTIMATE",
     "Coastal Cancer Centre, Mangaluru. Estimate CCC/26/740 dated 15/09/2026. Patient Abdul Rahman 55 M. Wide excision "
     "with neck dissection and flap. Total estimate Rs 2,80,000. Billing Manager (signed)")],
  env(stated=280000, inst="INCONCLUSIVE"), nmi("Provide the treating centre's own diagnosis."),
  note="Spelling of the name differs; treatment moved between institutions.")

S("FE-BC-MED-03", "BC", "borderline", "complete", "MEDICAL", "Physiotherapy after stroke for Sudha",
  "Sudha Iyer, 70, had a stroke. She needs three months of physiotherapy and a home nurse. The estimate is attached.",
  135000, "Sudha Iyer", "SELF", "Chennai", "Tamil Nadu", "2026-11-13",
  [D("Rehabilitation estimate", "HOSPITAL_ESTIMATE",
     "Adyar Rehabilitation Centre, Chennai. Estimate ARC/26/219 dated 09/11/2026. Patient Sudha Iyer 70 F. Physiotherapy "
     "60 sessions Rs 54,000; home nurse 3 months Rs 72,000. Total estimate Rs 1,26,000. Billing Executive (signed)"),
   D("Neurology note", "CLINICAL_NOTE",
     "Adyar Rehabilitation Centre. 08/11/2026. Sudha Iyer 70 F. Left hemiparesis after ischaemic stroke. Advised intensive "
     "physiotherapy. Dr L. Raman")],
  env(stated=126000), approve(), note="Goal is 7% above the estimate (just beyond a 5% tolerance).")

S("FE-BC-MED-04", "BC", "borderline", "complete", "MEDICAL", "Thalassaemia transfusions for Zoya",
  "Zoya Siddiqui, 12, needs monthly blood transfusions and iron chelation for thalassaemia. We ask for one year of "
  "treatment. The hospital's estimate covers chelation; the blood bank charges separately.",
  150000, "Zoya Siddiqui", "SELF", "Bhopal", "Madhya Pradesh", "2026-10-11",
  [D("Treatment estimate", "HOSPITAL_ESTIMATE",
     "Hamidia Thalassaemia Day Care, Bhopal. Estimate HTDC/26/88 dated 06/10/2026. Patient Zoya Siddiqui 12 F. "
     "Deferasirox chelation 12 months Rs 96,000. Total Rs 96,000. Accounts Officer (signed)"),
   D("Haematology note", "CLINICAL_NOTE",
     "Hamidia Thalassaemia Day Care. 05/10/2026. Zoya Siddiqui 12 F. Beta thalassaemia major on monthly transfusion. "
     "Ferritin 3,200. Continue chelation. Dr F. Khan")],
  env(stated=96000, issuer="CONFIRMED"), nmi("Provide the blood bank's charges."),
  note="Part of the goal is not documented; possibly genuine.")

S("FE-BC-EDU-01", "BC", "borderline", "complete", "EDUCATION", "Two years of fees for Nikhil",
  "Nikhil Jha is in a two-year diploma in pharmacy. We are raising both years' fees now so he does not drop out.",
  140000, "Nikhil Jha", "SELF", "Darbhanga", "Bihar", "2026-09-27",
  [D("Fee demand", "FEE_DEMAND",
     "Mithila Pharmacy College, Darbhanga. Demand MPC/26/512 dated 22/09/2026. Student Nikhil Jha, Roll DP26-044, D.Pharm "
     "Year 1. Annual fee Rs 70,000. Total Rs 70,000. Accounts Clerk (signed)"),
   D("Fee structure", "FEE_STRUCTURE",
     "Mithila Pharmacy College. Fee structure 2026-28. D.Pharm annual fee Rs 70,000 for each of two years. Principal")],
  env(stated=70000), approve(), note="Goal covers a second year that is not yet due.")

S("FE-BC-EDU-02", "BC", "borderline", "complete", "EDUCATION", "College fees for Mohammed Arif",
  "Mohd. Arif is in the first year of B.Sc at Aligarh Science College. The fee demand and his marksheet are attached.",
  48000, "Mohd. Arif", "SELF", "Aligarh", "Uttar Pradesh", "2026-10-04",
  [D("Fee demand", "FEE_DEMAND",
     "Aligarh Science College. Demand ASC/26/1771 dated 29/09/2026. Student Mohammed Arif Khan, Roll BSC26-219, B.Sc Year 1. "
     "Total Rs 48,000. Accounts Officer (signed)"),
   D("Class 12 marksheet", "MARKSHEET",
     "UP Board. Intermediate marksheet 2026. Mohd Arif, Roll 2611904. Aggregate 71 percent.")],
  env(stated=48000), nmi("Clarify the student's full name."), note="Name written in different forms.")

S("FE-BC-EDU-03", "BC", "borderline", "complete", "EDUCATION", "Fees paid to the student's mother",
  "Pallavi Kulkarni is in the second year of BCA. Please send the money to her mother's account; her mother pays the "
  "college.",
  72000, "Pallavi Kulkarni", "SELF", "Belagavi", "Karnataka", "2026-11-05",
  [D("Fee demand", "FEE_DEMAND",
     "Belgaum Institute of Computer Applications. Demand BICA/26/402 dated 30/10/2026. Student Pallavi Kulkarni, Roll "
     "BCA25-088, BCA Year 2. Total Rs 72,000. Accounts Officer (signed)"),
   D("Bank details", "BANK_DETAILS",
     "Account holder: Shobha Kulkarni (mother of Pallavi Kulkarni). Karnataka Bank, Account No. 7712003344558.")],
  env(stated=72000, pay="INCONCLUSIVE"), flag("SUSPECTED_FRAUD", "Funds go to a different person, not the college.",
                                              "Bank details", "Account holder: Shobha Kulkarni"),
  note="Payee is a parent: plausible but outside the institution.")

S("FE-BC-COM-01", "BC", "borderline", "complete", "COMMUNITY", "Library and generator for Dhamtari school",
  "Gyan Deep Society will set up a library at a government school in Dhamtari. The quotation also includes a generator "
  "for the school.",
  165000, "Gyan Deep Society", "ORGANISATION", "Dhamtari", "Chhattisgarh", "2026-10-16",
  [D("Quotation", "QUOTATION",
     "Chhattisgarh Book House, Raipur. Quotation CBH/26/377 dated 12/10/2026 for Gyan Deep Society: 1,200 books Rs 90,000; "
     "shelves Rs 30,000; 5 kVA generator Rs 45,000. Total Rs 1,65,000. Proprietor"),
   D("Society registration", "REGISTRATION",
     "Registration certificate. Gyan Deep Society registered under the Societies Registration Act, Reg. No. "
     "DMT/SOC/62/2017. Secretary: K. Sahu")],
  env(stated=165000), approve(), note="A generator from a bookseller is outside the stated purpose.")

S("FE-BC-COM-02", "BC", "borderline", "complete", "COMMUNITY", "Blankets for 120 families",
  "Himalayan Sewa Samiti will give winter blankets to 120 families in Kinnaur. The quotation is attached.",
  96000, "Himalayan Sewa Samiti", "ORGANISATION", "Reckong Peo", "Himachal Pradesh", "2026-11-10",
  [D("Blanket quotation", "QUOTATION",
     "Kullu Woollens, Kullu. Quotation KW/26/91 dated 05/11/2026 for Himalayan Sewa Samiti: 120 woollen blankets at Rs 800 "
     "each. Total Rs 96,000. Proprietor"),
   D("Panchayat letter", "LETTER",
     "Gram Panchayat Kalpa. 03/11/2026. 80 households in our panchayat need winter blankets. Pradhan, Kalpa"),
   D("Samiti registration", "REGISTRATION",
     "Registration certificate. Himalayan Sewa Samiti registered under the HP Societies Registration Act, Reg. No. "
     "KNR/SOC/12/2015. President: N. Negi")],
  env(stated=96000), flag("CONTRADICTION", "The panchayat counts 80 households but the campaign is for 120 families.",
                          "Panchayat letter", "80 households in our panchayat need winter blankets"),
  note="120 families vs 80 households.")

S("FE-BC-COM-03", "BC", "borderline", "complete", "COMMUNITY", "Repairs for the Sundarbans health sub-centre",
  "Sabuj Sangha will repair the health sub-centre at Gosaba. Our registration expired last month; the renewal receipt "
  "is attached with the contractor's quotation.",
  118000, "Sabuj Sangha", "ORGANISATION", "Gosaba", "West Bengal", "2026-10-30",
  [D("Repair quotation", "QUOTATION",
     "Sundarban Builders, Canning. Quotation SB/26/210 dated 24/10/2026 for Sabuj Sangha: roof, plaster and painting of "
     "the Gosaba health sub-centre. Total Rs 1,18,000. Proprietor"),
   D("Registration certificate", "REGISTRATION",
     "Registration certificate. Sabuj Sangha registered under the WB Societies Registration Act, Reg. No. S/2L/1123. "
     "Valid till 30/09/2026. Registrar"),
   D("Renewal receipt", "RECEIPT",
     "Office of the Registrar of Firms, Societies and Non-Trading Corporations. Receipt RFS/26/5521 dated 15/10/2026. "
     "Renewal fee received from Sabuj Sangha. Cashier")],
  env(stated=118000, inst="INCONCLUSIVE"), nmi("Provide the renewed registration certificate."),
  note="Registration lapsed; renewal in progress.")


def validate() -> None:
    ids = [s["case_id"] for s in SCENARIOS]
    assert len(ids) == 60 and len(set(ids)) == 60, (len(ids), len(set(ids)))
    counts = {k: sum(s["stratum"] == k for s in SCENARIOS) for k in ("FD", "FS", "LC", "LI", "BC")}
    assert counts == {"FD": 15, "FS": 10, "LC": 15, "LI": 10, "BC": 10}, counts
    for s in SCENARIOS:
        g = s["gemini_script"]
        if g["kind"] == "flag":
            doc = next(d for d in s["input"]["documents"] if d["title"] == g["document"])
            assert g["quote"] in doc["content"], (s["case_id"], g["quote"])


def write() -> Path:
    validate()
    OUT.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in SCENARIOS), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(write())
