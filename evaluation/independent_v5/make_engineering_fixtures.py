"""Synthetic ENGINEERING fixtures for testing the v5 tooling.  NOT independent test data.

Written by the developer's assistant to exercise the validator, runner and scorer end to end.  Every fixture ID
starts with ENG-; the runner refuses them in a live run, the validator refuses them under the full profile, and the
exclusion registry lists them so no fixture text can ever enter the independent test.
"""
import csv
import json
from pathlib import Path

from . import config

AUTHOR = "ENG-A01"


def _env(beneficiary="CONFIRMED", payee="CONFIRMED", institution="CONFIRMED", cost="CONFIRMED", stated=None,
         other=None, supplied=None, notes=None):
    notes = notes or {}
    env = {"BENEFICIARY": {"independent_response": beneficiary, "note": notes.get("b", "Platform KYC result.")},
           "PAYMENT_DESTINATION": {"independent_response": payee, "note": notes.get("p", "Account-holder name check.")},
           "INSTITUTION": {"independent_response": institution, "note": notes.get("i", "Official directory contact.")},
           "COST_ISSUER": {"independent_response": cost, "amount_stated_inr": stated, "other_payers_inr": other,
                           "note": notes.get("c", "Billing or accounts office, official channel.")}}
    if supplied:
        env["INSTITUTION"]["campaign_supplied_contact"] = {"printed_in_uploads": True, "response": "CONFIRMED",
                                                           "note": "Number printed on the letterhead reaches a confederate."}
    return env


def _case(cid, category, label, documentation, title, story, goal, beneficiary, city, state, submitted, documents,
          env, gold=None, mechanism=None, form=None, keyword_free=False, subtype=None, date_sensitive=False,
          date_facts=None, beneficiary_type="SELF", detectable=None):
    group = cid.rsplit("-", 1)[0]
    return {"case_id": cid, "scenario_group": group, "author_id": AUTHOR, "provenance": "synthetic", "synthetic": True,
            "llm_assisted": True, "engineering_fixture": True, "category": category, "author_intended_label": label,
            "author_intended_documentation": documentation, "mechanism": mechanism, "form": form,
            "keyword_free": keyword_free, "incomplete_subtype": subtype, "date_sensitive": date_sensitive,
            "intended_detectable_from_dossier": detectable if label == "fraudulent" else None,
            "date_facts": date_facts or [],
            "input": {"title": title, "category": category, "story": story, "goal_amount": goal, "goal_currency": "INR",
                      "beneficiary_name": beneficiary, "beneficiary_type": beneficiary_type, "city": city, "state": state,
                      "submitted_on": submitted,
                      "documents": [{"title": t, "doc_type": d, "content": c} for t, d, c in documents]},
            "gold_evidence_titles": gold or [], "external_environment": env}


def _long_rehab_chart() -> str:
    exercises = ["quadriceps sets", "heel slides", "straight leg raises", "ankle pumps", "terminal knee extension",
                 "mini squats against wall", "step-ups on low stool", "stationary cycling", "hamstring curls",
                 "patellar mobilisation"]
    medicines = ["tab paracetamol 650 mg", "tab pantoprazole 40 mg", "cap pregabalin 75 mg", "tab aceclofenac 100 mg",
                 "inj enoxaparin 40 mg", "tab calcium with vitamin D3"]
    remarks = ["walked to washroom with walker", "wound dry, dressing changed", "mild swelling over medial joint line",
               "slept well, no night pain", "climbed four steps with railing", "ice pack applied twice",
               "independent transfers from bed", "knee flexion improving steadily", "gait trained in corridor",
               "family taught home exercise plan"]
    lines = ["ARUNODAYA ORTHO HOSPITAL, SALEM - INPATIENT REHABILITATION CHART (PLANNED PROTOCOL)"]
    for day in range(1, 61):
        lines.append(f"Day {day}: {exercises[day % len(exercises)]} {2 + day % 3} sets of {10 + day % 6}; "
                     f"{medicines[day % len(medicines)]} after food; flexion target {60 + day} degrees; "
                     f"{remarks[(day * 3) % len(remarks)]}; physiotherapist initials RK/{day:02d}.")
    return "\n".join(lines)


def cases() -> list:
    return [
        _case("ENG-MED-0001-A", "MEDICAL", "legitimate", "complete", "Knee replacement for Lakshmi amma",
              "Lakshmi Iyer is 61 and has severe osteoarthritis of the right knee. Her orthopaedic surgeon at Arunodaya "
              "Ortho Hospital has planned a total knee replacement. Her son drives an auto-rickshaw and we have saved "
              "part of the amount. The hospital estimate and the rehabilitation plan are attached.",
              240000, "Lakshmi Iyer", "Salem", "Tamil Nadu", "2027-02-20",
              [("Hospital estimate TKR", "HOSPITAL_ESTIMATE",
                "Arunodaya Ortho Hospital, Omalur Road, Salem 636009. Ph 0427-000-1180\nEstimate No. AOH/EST/2027/311   Date: 14/02/2027\n"
                "Patient: Lakshmi Iyer, 61 F, UHID AOH-77120\nProcedure: Right total knee replacement (cemented)\n"
                "Implant Rs 1,10,000; Surgery and OT Rs 70,000; Ward 5 days Rs 35,000; Physiotherapy Rs 25,000\n"
                "Total estimate Rs 2,40,000. Proposed date of surgery: 12/03/2027. Billing Manager (signed)"),
               ("Orthopaedic consultation", "CLINICAL_NOTE",
                "Arunodaya Ortho Hospital OPD 12/02/2027. Lakshmi Iyer 61 F. Grade IV osteoarthritis right knee on "
                "standing X-ray, varus deformity, failed 2 years of conservative care. Advised right TKR. Dr S. Raghavan MS Ortho"),
               ("Rehabilitation chart", "CARE_PLAN", _long_rehab_chart())],
              _env(stated=240000, other=0), date_sensitive=True,
              date_facts=[{"document_title": "Hospital estimate TKR", "as_written": "14/02/2027", "date": "2027-02-14", "role": "issue"},
                          {"document_title": "Hospital estimate TKR", "as_written": "12/03/2027", "date": "2027-03-12",
                           "role": "scheduled_event"}]),
        _case("ENG-MED-0001-B", "MEDICAL", "legitimate", "complete", "Physiotherapy after Lakshmi's knee surgery",
              "After her knee operation Lakshmi needs eight weeks of outpatient physiotherapy near home in Salem. The "
              "rehabilitation centre has given a written quotation for the sessions and a home exercise kit.",
              45000, "Lakshmi Iyer", "Salem", "Tamil Nadu", "2027-02-22",
              [("Physiotherapy quotation", "QUOTATION",
                "Kaveri Rehab Centre, Fairlands, Salem. GSTIN 33AAAAK0000A1Z5\nQuotation Q-2027-0458 dated 18/02/2027\n"
                "Client: Lakshmi Iyer. 40 sessions x Rs 950 = Rs 38,000; exercise kit Rs 7,000. Total Rs 45,000. "
                "Validity 60 days. Authorised signatory: M. Selvi"),
               ("Referral letter", "CLINICAL_NOTE",
                "Referral to Kaveri Rehab Centre for post TKR rehabilitation of Lakshmi Iyer, 61, after surgery on 12/03/2027. Dr S. Raghavan")],
              _env(stated=45000, other=0)),
        _case("ENG-MED-0002-A", "MEDICAL", "legitimate", "incomplete", "Dialysis support for Farid bhai",
              "Farid Ansari has kidney failure and goes for dialysis three times a week at the district hospital. The "
              "consumables and injections are bought outside. We are asking for six months of support.",
              90000, "Farid Ansari", "Bareilly", "Uttar Pradesh", "2027-01-15",
              [("Nephrology note", "CLINICAL_NOTE",
                "District Hospital Bareilly, Nephrology unit. Farid Ansari 47 M. CKD stage 5 on maintenance haemodialysis "
                "thrice weekly since 2026. Requires erythropoietin injections and dialyser kits. Dr N. Khan")],
              _env(cost="INCONCLUSIVE", stated=None, other=None), gold=["Nephrology note"], subtype="no_cost_document"),
        _case("ENG-MED-0003-A", "MEDICAL", "fraudulent", "complete", "Bypass surgery for my father",
              "My father Gopal Rao was admitted on 20 January for heart bypass surgery at Sunrise Heart Centre. "
              "We have arranged some of the money and request help for the remaining bill.",
              310000, "Gopal Rao", "Vijayawada", "Andhra Pradesh", "2027-02-01",
              [("Admission note", "ADMISSION_RECORD",
                "Sunrise Heart Centre, Vijayawada. Patient Gopal Rao 66 M, IP No. SHC-20981. Admitted on 20/01/2027 for "
                "CABG. Estimated cost Rs 3,10,000. Ref SHC/ADM/0981. Dr K. Murthy"),
               ("Death certificate", "DEATH_CERTIFICATE",
                "Government of Andhra Pradesh, Registrar of Births and Deaths, Vijayawada. Name: Gopal Rao, male, 66. "
                "Date of death: 05/01/2027. Place of death: residence. Registration No. VJA-D-2027-00412")],
              _env(institution="CONTRADICTED", cost="CONTRADICTED", stated=None, notes={"i": "No admission on record."}),
              gold=["Death certificate", "Admission note"], mechanism="document_contradiction", form="structured", detectable=True,
              date_sensitive=True,
              date_facts=[{"document_title": "Death certificate", "as_written": "05/01/2027", "date": "2027-01-05", "role": "death"},
                          {"document_title": "Admission note", "as_written": "20/01/2027", "date": "2027-01-20",
                           "role": "completed_event"}]),
        _case("ENG-MED-0004-A", "MEDICAL", "fraudulent", "complete", "Cataract operation for Savitri",
              "Savitri Devi, 70, is losing her sight from cataract in both eyes. Netra Jyoti Eye Hospital has given an "
              "estimate for operating on both eyes. Her pension is small and we ask for your kindness.",
              330000, "Savitri Devi", "Gaya", "Bihar", "2027-01-28",
              [("Eye hospital estimate", "HOSPITAL_ESTIMATE",
                "Netra Jyoti Eye Hospital, Station Road, Gaya. Estimate EJ/2027/1203 dated 22/01/2027. Patient Savitri "
                "Devi 70 F. Phaco with foldable IOL, both eyes, Rs 55,000 per eye. Total Rs 1,10,000. Cashier (seal)"),
               ("Eye examination", "CLINICAL_NOTE",
                "Netra Jyoti Eye Hospital OPD. Savitri Devi. Mature senile cataract both eyes, vision counting fingers "
                "at 2 metres. Advised phacoemulsification. Dr A. Sinha")],
              _env(cost="CONFIRMED", stated=110000, other=0, notes={"c": "Billing states Rs 1,10,000 for both eyes."}),
              gold=["Eye hospital estimate"], mechanism="amount_inflation", keyword_free=True, detectable=True),
        _case("ENG-MED-0005-A", "MEDICAL", "borderline", "complete", "Spine surgery for Ravikumar",
              "Ravikumar Murthy injured his back lifting cement bags. A clinic has quoted for a spine operation. "
              "We are a family of daily-wage workers and need support.",
              180000, "Ravikumar Murthy", "Tumakuru", "Karnataka", "2027-02-05",
              [("Clinic quotation", "QUOTATION",
                "Shree Spine Clinic, Tumakuru. Quotation 2027/88 dated 30/01/2027 for Ravi Kumar M., lumbar "
                "discectomy L4-L5, Rs 1,80,000 all inclusive. Dr P. Hegde"),
               ("MRI report", "DIAGNOSTIC_REPORT",
                "Tumakuru Scans. Ravikumar Murthy 39 M. MRI lumbar spine: L4-L5 disc bulge without nerve root "
                "compression. Clinical correlation advised.")],
              _env(institution="INCONCLUSIVE", cost="CONFIRMED", stated=180000, other=0),
              gold=["MRI report", "Clinic quotation"]),
        _case("ENG-MED-0006-A", "MEDICAL", "legitimate", "incomplete", "Hernia repair for a mason",
              "A mason from our village needs a hernia operation so he can return to work. The hospital gave a bill "
              "estimate. He does not want his name shown publicly.",
              60000, "Not disclosed", "Nashik", "Maharashtra", "2027-02-11",
              [("Hernia estimate", "HOSPITAL_ESTIMATE",
                "Godavari General Hospital, Nashik. Estimate GGH/EST/7781 dated 06/02/2027. Open mesh hernioplasty, "
                "2 days stay, Rs 60,000. Accounts section (stamp)")],
              _env(beneficiary="INCONCLUSIVE", stated=60000, other=0), gold=["Hernia estimate"],
              subtype="missing_identity_or_need"),
        _case("ENG-EDU-0001-A", "EDUCATION", "legitimate", "complete", "Second-year engineering fees for Meghna",
              "Meghna Das is in the second year of B.Tech in Electronics at Kalinga Institute of Engineering. Her "
              "father's shop closed last year. The college fee demand for this year is attached with her ID card.",
              98000, "Meghna Das", "Bhubaneswar", "Odisha", "2027-02-10",
              [("Fee demand 2026-27", "FEE_DEMAND",
                "Kalinga Institute of Engineering, Patia, Bhubaneswar 751024. Accounts Office\nDemand No. KIE/ACC/2027/5520   Date 02/02/2027\n"
                "Student: Meghna Das, Roll 24ECE118, B.Tech ECE Year 2. Tuition Rs 82,000; Exam Rs 6,000; Lab Rs 10,000. "
                "Total Rs 98,000. Last date for payment: 31/03/2027. Accounts Officer (signed)"),
               ("Student identity card", "IDENTITY",
                "Kalinga Institute of Engineering. Identity card. Meghna Das, B.Tech ECE, Roll 24ECE118, valid till 2028.")],
              _env(stated=98000, other=0), date_sensitive=True,
              date_facts=[{"document_title": "Fee demand 2026-27", "as_written": "02/02/2027", "date": "2027-02-02", "role": "issue"},
                          {"document_title": "Fee demand 2026-27", "as_written": "31/03/2027", "date": "2027-03-31",
                           "role": "validity_end"}]),
        _case("ENG-EDU-0002-A", "EDUCATION", "legitimate", "incomplete", "Coaching for Pooja's board exams",
              "Pooja is in class 12 in a government school and attends evening tuition with a retired teacher in our "
              "colony. He charges a small monthly amount and does not issue receipts. We ask for help for six months.",
              18000, "Pooja Yadav", "Rewari", "Haryana", "2027-01-18",
              [("Teacher's note", "LETTER",
                "To whom it may concern. Pooja Yadav studies mathematics and physics with me every evening for her "
                "class 12 examinations. My monthly charge is Rs 3,000. R. S. Yadav, retired lecturer")],
              _env(institution="CONFIRMED", cost="CONFIRMED", stated=18000, other=0), gold=["Teacher's note"],
              subtype="genuine_but_informal"),
        _case("ENG-EDU-0003-A", "EDUCATION", "fraudulent", "complete", "Nursing course fees for Anjali",
              "Anjali Thomas has been admitted to the B.Sc Nursing course at St. Mary's College of Nursing. Please "
              "contribute so she can complete her first year.",
              120000, "Anjali Thomas", "Kottayam", "Kerala", "2027-01-25",
              [("Admission letter", "ADMISSION_LETTER",
                "St. Mary's College of Nursing, Kottayam. Ref SMCN/ADM/2026/214 dated 12/12/2026. Anjali Thomas is "
                "admitted to B.Sc Nursing 2026-27. Annual fee Rs 1,20,000. Principal"),
               ("Payout details", "BANK_DETAILS",
                "Account name: Edu Path Admissions Consultancy. Bank: Kottayam Co-operative Bank. A/c 00000123456")],
              _env(payee="CONTRADICTED", stated=120000, other=0,
                   notes={"p": "Account belongs to an admissions agent, not the college or the student."}),
              gold=["Payout details"], mechanism="suspicious_payee", detectable=True),
        _case("ENG-EDU-0004-A", "EDUCATION", "fraudulent", "complete", "Final-year MBA fees for Rohit",
              "Rohit Verma is in the final year of his MBA at Doon School of Management and needs the last instalment.",
              150000, "Rohit Verma", "Dehradun", "Uttarakhand", "2027-02-03",
              [("College certificate", "LETTER",
                "Doon School of Management, Dehradun. Certificate No. DSM/CERT/889 dated 15/01/2027. This is to certify "
                "that Rohit Verma, Roll MBA/2023/041, was a student of the MBA programme 2023-2025 and received his "
                "degree in convocation held on 10/08/2025. Registrar"),
               ("Fee schedule", "FEE_DEMAND",
                "Doon School of Management. MBA programme fee schedule. Final-year instalment Rs 1,50,000.")],
              _env(institution="CONTRADICTED", stated=None, cost="INCONCLUSIVE",
                   notes={"i": "Registrar confirms the student graduated in 2025."}),
              gold=["College certificate"], mechanism="misrepresented_need", detectable=True),
        _case("ENG-EDU-0005-A", "EDUCATION", "borderline", "complete", "Diploma in aviation for Sameer",
              "Sameer wants to become an aircraft maintenance engineer. He has an offer from SkyWings Aviation Academy.",
              260000, "Sameer Khan", "Indore", "Madhya Pradesh", "2027-01-30",
              [("Offer letter", "ADMISSION_LETTER",
                "SkyWings Aviation Academy, Indore. Offer No. SWA/OFF/2027/77 dated 20/01/2027. Sameer Khan is offered "
                "a seat in the Aircraft Maintenance Engineering diploma. Programme fee Rs 2,60,000. Director (signed)")],
              _env(institution="INCONCLUSIVE", stated=260000, other=0,
                   notes={"i": "Academy found online but its approval status could not be confirmed."}),
              gold=["Offer letter"]),
        _case("ENG-COM-0001-A", "COMMUNITY", "legitimate", "complete", "Borewell for Hanumanthapura school",
              "Hanumanthapura government primary school has no reliable water. Gram Seva Trust will drill a borewell "
              "with a hand pump. Two supplier quotations and our registration are attached.",
              175000, "Gram Seva Trust", "Chitradurga", "Karnataka", "2027-02-14",
              [("Drilling quotation", "QUOTATION",
                "Sri Lakshmi Borewells, Chitradurga. GSTIN 29AAAAS0000B1Z2. Quotation SLB/Q/2027/031 dated 08/02/2027 "
                "for Gram Seva Trust: drilling 450 ft Rs 1,12,500; casing pipe Rs 32,500; hand pump fitting Rs 30,000. "
                "Total Rs 1,75,000. Proprietor"),
               ("Second quotation", "QUOTATION",
                "Durga Rigs, Hosadurga. Quotation DR/2027/19 dated 09/02/2027. Borewell 450 ft with hand pump for "
                "Hanumanthapura school, Rs 1,86,000. Manager"),
               ("Trust registration", "REGISTRATION",
                "Registration certificate. Gram Seva Trust registered under the Indian Trusts Act, Reg. No. CTA-IV-118/2019. "
                "Managing trustee: K. Shivanna")],
              _env(stated=175000, other=0), beneficiary_type="ORGANISATION"),
        _case("ENG-COM-0002-A", "COMMUNITY", "legitimate", "incomplete", "Ramp and toilet for the anganwadi",
              "The anganwadi in Ward 7 needs a ramp and an accessible toilet for children with disabilities. "
              "Our women's self-help group will oversee the work.",
              95000, "Saheli Mahila Mandal", "Jalgaon", "Maharashtra", "2027-01-20",
              [("Contractor quotation", "QUOTATION",
                "Patil Constructions, Jalgaon. Quotation PC/2026/310 dated 01/10/2026 for Saheli Mahila Mandal: ramp "
                "and accessible toilet at Ward 7 anganwadi, Rs 95,000. Valid until 15/12/2026. Contractor"),
               ("Society registration", "REGISTRATION",
                "Saheli Mahila Mandal, registered under the Societies Registration Act 1860, No. MH/JAL/2015/442.")],
              _env(cost="CONFIRMED", stated=104000, other=0, notes={"c": "Contractor now quotes Rs 1,04,000."}),
              gold=["Contractor quotation"], subtype="unacceptable_cost_document", beneficiary_type="ORGANISATION",
              date_sensitive=True,
              date_facts=[{"document_title": "Contractor quotation", "as_written": "15/12/2026", "date": "2026-12-15",
                           "role": "validity_end"}]),
        _case("ENG-COM-0003-A", "COMMUNITY", "fraudulent", "complete", "Shelter for injured street animals",
              "Karuna Jeev Raksha Trust runs a small shelter for injured cows and dogs on the highway. We need a shed "
              "and a treatment room before the monsoon.",
              400000, "Karuna Jeev Raksha Trust", "Udaipur", "Rajasthan", "2027-01-26",
              [("Trust deed extract", "REGISTRATION",
                "Karuna Jeev Raksha Trust, Udaipur. Trust deed registration No. UDR/TR/2018/0771. Trustees: M. Jain, "
                "R. Meena. Office: 14 Fatehpura, Udaipur. Ph 0294-000-7712"),
               ("Shed estimate", "QUOTATION",
                "Aravali Fabricators, Udaipur. Estimate AF/2027/12 dated 15/01/2027 for Karuna Jeev Raksha Trust: steel "
                "shed 60x30 ft Rs 2,90,000; treatment room Rs 1,10,000. Total Rs 4,00,000. Proprietor")],
              _env(institution="CONTRADICTED", supplied=True, cost="UNREACHABLE", stated=None,
                   notes={"i": "Registrar has no trust with this number."}),
              gold=["Trust deed extract"], mechanism="consistent_fabrication", beneficiary_type="ORGANISATION", detectable=False),
        _case("ENG-COM-0003-B", "COMMUNITY", "fraudulent", "complete", "Bird rescue ward in Udaipur",
              "The same trust volunteers rescue birds hurt by kite strings every January and want an aviary ward with "
              "cages, a small operating table and medicines for the season.",
              150000, "Karuna Jeev Raksha Trust", "Udaipur", "Rajasthan", "2027-01-27",
              [("Aviary quotation", "QUOTATION",
                "Mewar Wire Works, Udaipur. Quotation MWW/2027/05 dated 16/01/2027. Aviary cages 20 units Rs 90,000; "
                "steel operating table Rs 25,000; installation Rs 35,000. Total Rs 1,50,000. Owner"),
               ("Volunteer letter", "LETTER",
                "Karuna Jeev Raksha Trust letterhead. Our volunteers treated 312 birds during last year's kite season. "
                "Signed, M. Jain, trustee")],
              _env(institution="CONTRADICTED", supplied=True, cost="CONFIRMED", stated=150000, other=0),
              gold=["Volunteer letter"], mechanism="consistent_fabrication", beneficiary_type="ORGANISATION", detectable=False),
        _case("ENG-COM-0004-A", "COMMUNITY", "fraudulent", "complete", "New roof for the village library",
              "The roof of the Ambedkar reading room in Sonpur leaks over the bookshelves. Navjyoti Yuva Mandal has a "
              "contractor's estimate and asks villagers abroad to help.",
              85000, "Navjyoti Yuva Mandal", "Sonpur", "Bihar", "2027-02-09",
              [("Roof estimate", "QUOTATION",
                "Saran Builders, Chhapra. Estimate SB/2027/044 dated 01/02/2027 for Navjyoti Yuva Mandal: replace "
                "asbestos roof of reading room with GI sheets, 600 sq ft, Rs 85,000. Partner"),
               ("Mandal registration", "REGISTRATION",
                "Navjyoti Yuva Mandal, Sonpur, registered society No. BR/SAR/2012/219. Secretary: A. Paswan")],
              _env(institution="CONFIRMED", cost="CONTRADICTED", stated=85000, other=85000,
                   notes={"c": "Builder states the panchayat grant settled this work in January."}),
              gold=["Roof estimate"], mechanism="independent_record_contradiction", beneficiary_type="ORGANISATION",
              keyword_free=True, detectable=False),
        _case("ENG-COM-0005-A", "COMMUNITY", "borderline", "complete", "Community kitchen during harvest",
              "Volunteers in Malda want to run a community kitchen for migrant farm workers for two months.",
              70000, "Annapurna Seva Samiti", "Malda", "West Bengal", "2027-02-12",
              [("Kitchen budget", "BUDGET",
                "Annapurna Seva Samiti. Kitchen budget for 60 days: rice and dal Rs 42,000; vegetables Rs 14,000; fuel "
                "Rs 9,000; utensils Rs 5,000. Total Rs 70,000. Prepared by the secretary on 05/02/2027")],
              _env(institution="INCONCLUSIVE", cost="INCONCLUSIVE", stated=None), gold=["Kitchen budget"],
              beneficiary_type="ORGANISATION"),
    ]


def pilot_cases() -> list:
    return [
        _case("ENG-PIL-0001-A", "MEDICAL", "legitimate", "complete", "Gallbladder surgery for Rekha",
              "Rekha Kumari needs laparoscopic gallbladder removal at Patliputra Surgical Centre; the estimate is attached.",
              65000, "Rekha Kumari", "Patna", "Bihar", "2027-02-02",
              [("Surgical estimate", "HOSPITAL_ESTIMATE",
                "Patliputra Surgical Centre, Kankarbagh, Patna. Estimate PSC/E/2027/120 dated 28/01/2027. Rekha Kumari "
                "34 F. Laparoscopic cholecystectomy Rs 65,000 inclusive. Billing (signed)")],
              _env(stated=65000, other=0)),
        _case("ENG-PIL-0002-A", "EDUCATION", "legitimate", "incomplete", "Hostel fees for Arjun",
              "Arjun studies at a polytechnic in Hubballi and needs help with hostel charges for this semester.",
              30000, "Arjun Patil", "Hubballi", "Karnataka", "2027-01-21",
              [("Bonafide certificate", "LETTER",
                "Government Polytechnic, Hubballi. Bonafide certificate. Arjun Patil is a student of Diploma in Civil "
                "Engineering, second year. Principal")],
              _env(cost="INCONCLUSIVE", stated=None), gold=["Bonafide certificate"], subtype="no_cost_document"),
    ]


SCRIPT = {
    "ENG-MED-0001-A": ["approve"], "ENG-MED-0001-B": ["approve"], "ENG-MED-0002-A": ["nmi"],
    "ENG-MED-0003-A": ["flag_grounded"], "ENG-MED-0004-A": ["approve"],
    "ENG-MED-0005-A": ["SERVER_ERROR", "approve"], "ENG-MED-0006-A": ["invalid_json"],
    "ENG-EDU-0001-A": ["approve"], "ENG-EDU-0002-A": ["nmi"], "ENG-EDU-0003-A": ["approve"],
    "ENG-EDU-0004-A": ["flag_ungrounded"], "ENG-EDU-0005-A": ["READ_TIMEOUT", "READ_TIMEOUT"],
    "ENG-COM-0001-A": ["approve"], "ENG-COM-0002-A": ["approve"], "ENG-COM-0003-A": ["approve"],
    "ENG-COM-0003-B": ["approve"], "ENG-COM-0004-A": ["reject_ungrounded"], "ENG-COM-0005-A": ["nmi"],
    "ENG-PIL-0001-A": ["approve"], "ENG-PIL-0002-A": ["nmi"],
}

PARTICIPANTS = [
    {"participant_id": "ENG-A01", "role": "author"}, {"participant_id": "ENG-L01", "role": "labeller"},
    {"participant_id": "ENG-L02", "role": "labeller"}, {"participant_id": "ENG-J01", "role": "adjudicator"},
    {"participant_id": "ENG-C01", "role": "coordinator"},
]

# (truth, documentation, missing, dossier, external, decisive, amount, acceptable, date_check)
LABELS = {
    "ENG-MED-0001-A": ("legitimate", "complete", "", "", "", "Hospital estimate TKR", "240000", "APPROVED", "consistent"),
    "ENG-MED-0001-B": ("legitimate", "complete", "", "", "", "Physiotherapy quotation", "45000", "APPROVED", "n/a"),
    "ENG-MED-0002-A": ("legitimate", "incomplete", "COST", "", "", "Nephrology note", "", "NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-MED-0003-A": ("fraudulent", "complete", "", "yes", "yes", "Death certificate;Admission note", "",
                       "FLAG_FOR_REVIEW", "inconsistent"),
    "ENG-MED-0004-A": ("fraudulent", "complete", "", "yes", "yes", "Eye hospital estimate", "110000",
                       "FLAG_FOR_REVIEW;NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-MED-0005-A": ("borderline", "complete", "", "", "", "MRI report", "", "NEEDS_MORE_INFORMATION;FLAG_FOR_REVIEW", "n/a"),
    "ENG-MED-0006-A": ("legitimate", "incomplete", "ID", "", "", "Hernia estimate", "60000", "NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-EDU-0001-A": ("legitimate", "complete", "", "", "", "Fee demand 2026-27", "98000", "APPROVED", "consistent"),
    "ENG-EDU-0002-A": ("legitimate", "incomplete", "COST", "", "", "Teacher's note", "18000", "NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-EDU-0003-A": ("fraudulent", "complete", "", "yes", "yes", "Payout details", "",
                       "FLAG_FOR_REVIEW;NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-EDU-0004-A": ("fraudulent", "complete", "", "yes", "yes", "College certificate", "", "FLAG_FOR_REVIEW", "inconsistent"),
    "ENG-EDU-0005-A": ("borderline", "complete", "", "", "", "Offer letter", "", "NEEDS_MORE_INFORMATION;FLAG_FOR_REVIEW", "n/a"),
    "ENG-COM-0001-A": ("legitimate", "complete", "", "", "", "Drilling quotation", "175000", "APPROVED", "n/a"),
    "ENG-COM-0002-A": ("legitimate", "incomplete", "COST", "", "", "Contractor quotation", "", "NEEDS_MORE_INFORMATION",
                       "consistent"),
    "ENG-COM-0003-A": ("fraudulent", "complete", "", "no", "yes", "Trust deed extract", "",
                       "FLAG_FOR_REVIEW;NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-COM-0003-B": ("fraudulent", "complete", "", "no", "yes", "Volunteer letter", "",
                       "FLAG_FOR_REVIEW;NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-COM-0004-A": ("fraudulent", "complete", "", "no", "yes", "Roof estimate", "0",
                       "FLAG_FOR_REVIEW;NEEDS_MORE_INFORMATION", "n/a"),
    "ENG-COM-0005-A": ("borderline", "complete", "", "", "", "Kitchen budget", "", "NEEDS_MORE_INFORMATION;FLAG_FOR_REVIEW", "n/a"),
}
# labeller B disagrees on two cases; the adjudicator resolves both
B_OVERRIDES = {"ENG-MED-0005-A": {"truth_label": "legitimate", "acceptable_end_states": "APPROVED"},
               "ENG-COM-0005-A": {"documentation": "incomplete", "missing_items": "COST"}}
ADJUDICATION = [
    {"case_id": "ENG-MED-0005-A", "field": "truth_label", "adjudicated_value": "borderline",
     "reason": "The MRI shows no nerve compression; surgery may not be indicated."},
    {"case_id": "ENG-MED-0005-A", "field": "acceptable_end_states",
     "adjudicated_value": "NEEDS_MORE_INFORMATION;FLAG_FOR_REVIEW", "reason": "Follows the truth label."},
    {"case_id": "ENG-COM-0005-A", "field": "documentation", "adjudicated_value": "complete",
     "reason": "A self-prepared budget is the expected cost evidence for a volunteer kitchen."},
    {"case_id": "ENG-COM-0005-A", "field": "missing_items", "adjudicated_value": "-", "reason": "Follows documentation."},
]


def build(directory: Path = config.FIXTURES) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "submission.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases()),
                                                encoding="utf-8")
    (directory / "pilot.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in pilot_cases()),
                                           encoding="utf-8")
    (directory / "gemini_script.json").write_text(json.dumps(SCRIPT, indent=2) + "\n", encoding="utf-8")
    from .participants import FIELDS
    with (directory / "participants.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for p in PARTICIPANTS:
            writer.writerow({**p, "independence_declared": "yes", "involved_in_implementation": "no",
                             "involved_in_prior_benchmarks_or_tuning": "no", "saw_verifier_code_or_lexicons": "no",
                             "saw_prior_corpora": "no", "declared_on": "2027-01-05",
                             "notes": "ENGINEERING FIXTURE - not a real person"})
    from .labels import ADJUDICATION_FIELDS, SHEET_FIELDS
    for labeller, overrides in (("ENG-L01", {}), ("ENG-L02", B_OVERRIDES)):
        name = "labels_a.csv" if labeller == "ENG-L01" else "labels_b.csv"
        with (directory / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SHEET_FIELDS)
            writer.writeheader()
            for cid, (truth, doc, missing, dossier, external, decisive, amount, acceptable, date_check) in LABELS.items():
                row = {"case_id": cid, "labeller_id": labeller, "truth_label": truth, "documentation": doc,
                       "missing_items": missing, "detectable_from_dossier": dossier,
                       "detectable_by_external_confirmation": external, "decisive_evidence_titles": decisive,
                       "justified_amount_inr": amount, "acceptable_end_states": acceptable, "date_check": date_check,
                       "notes": ""}
                row.update(overrides.get(cid, {}))
                writer.writerow(row)
    with (directory / "adjudication.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_FIELDS)
        writer.writeheader()
        a = {cid: v for cid, v in LABELS.items()}
        for row in ADJUDICATION:
            base_a = dict(zip(["truth_label", "documentation", "missing_items", "detectable_from_dossier",
                               "detectable_by_external_confirmation", "decisive_evidence_titles", "justified_amount_inr",
                               "acceptable_end_states", "date_check"], a[row["case_id"]]))
            writer.writerow({"case_id": row["case_id"], "field": row["field"],
                             "labeller_a_value": base_a[row["field"]],
                             "labeller_b_value": B_OVERRIDES[row["case_id"]].get(row["field"], base_a[row["field"]]),
                             "adjudicated_value": row["adjudicated_value"], "adjudicator_id": "ENG-J01",
                             "reason": row["reason"]})
    (directory / "README.md").write_text(
        "# Engineering fixtures (NOT independent test data)\n\n"
        "Synthetic cases written by the developer's assistant to test the v5 validator, runner and scorer offline.\n"
        "Every ID starts with `ENG-`. The runner refuses them in a live run, the validator refuses them under the full\n"
        "profile, and `exclusion_registry.json` lists them so their text can never enter the independent test.\n"
        "The participants and labels here are fictional engineering placeholders, not real people.\n"
        "Regenerate with `python evaluation/prepare_independent_data_v5.py make-engineering-fixtures`.\n",
        encoding="utf-8")
    return {"cases": len(cases()), "pilot_cases": len(pilot_cases()), "directory": str(directory)}
