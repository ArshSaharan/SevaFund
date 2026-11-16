"""Generate the fixed, synthetic 200-case held-out fundraising evaluation set."""
import json
from pathlib import Path

OUT = Path(__file__).with_name("fundraising_scenarios.jsonl")


def add(rows, truth, category, subtype, title, story, goal, docs=(), beneficiary="Asha Mehta", beneficiary_type="FAMILY", city="Pune", state="Maharashtra"):
    rows.append({
        "case_id": f"SYN-{len(rows)+1:03d}",
        "ground_truth": truth,
        "scenario_group": subtype,
        "synthetic": True,
        "input": {
            "title": title,
            "category": category,
            "story": story,
            "goal_amount": goal,
            "beneficiary_name": beneficiary,
            "beneficiary_type": beneficiary_type,
            "city": city,
            "state": state,
            "documents": [
                {"doc_type": kind, "title": doc_title, "content": content}
                for kind, doc_title, content in docs
            ],
        },
    })


def build():
    rows = []
    people = ["Asha Mehta", "Rohan Kulkarni", "Mira Nair", "Kabir Deshmukh", "Leela Iyer", "Nikhil Sood", "Tara Menon", "Dev Shah", "Anaya Rao", "Ishaan Bhat"]
    cities = [("Pune", "Maharashtra"), ("Kochi", "Kerala"), ("Jaipur", "Rajasthan"), ("Chennai", "Tamil Nadu"), ("Hyderabad", "Telangana"), ("Ahmedabad", "Gujarat"), ("Bengaluru", "Karnataka"), ("Lucknow", "Uttar Pradesh"), ("Kolkata", "West Bengal"), ("Delhi", "Delhi")]
    conditions = [
        ("congenital valve disease", "heart surgery", 540000), ("severe aplastic anaemia", "treatment", 780000),
        ("chronic kidney failure", "dialysis", 165000), ("spinal injury after a bus collision", "surgery", 240000),
        ("retinoblastoma", "cancer treatment", 980000), ("complex burn injuries", "surgery", 390000),
        ("premature birth complications", "NICU care", 620000), ("liver disease requiring transplant evaluation", "organ transplant", 2100000),
        ("drug-resistant tuberculosis", "treatment", 310000), ("severe scoliosis", "surgery", 420000),
        ("rheumatic valve damage", "heart surgery", 670000), ("lymphoma", "chemotherapy", 860000),
        ("renal failure", "dialysis", 135000), ("brain aneurysm", "surgery", 480000),
        ("acute pancreatitis", "ICU care", 330000), ("osteosarcoma", "cancer treatment", 1150000),
        ("neonatal respiratory distress", "NICU care", 450000), ("spinal tuberculosis", "surgery", 290000),
        ("severe aplastic anaemia", "treatment", 690000), ("corneal damage after infection", "surgery", 175000),
    ]
    hospitals = ["Kokilaben Dhirubhai Ambani Hospital", "Narayana Health City", "CMC Vellore", "Medanta Lucknow", "KEM Hospital", "PGIMER Chandigarh", "Manipal Hospital", "Sir Ganga Ram Hospital", "Hinduja Hospital", "Narayana Multispeciality Hospital"]
    doctors = ["Dr. Kavita Rao", "Dr. Sameer Pillai", "Dr. Farah Khan", "Dr. Arjun Bose", "Dr. Neha Kulkarni", "Dr. Vivek Menon"]
    for i in range(60):
        person = people[i % len(people)]
        condition, treatment, base = conditions[i % len(conditions)]
        city, state = cities[(i * 3) % len(cities)]
        hospital = hospitals[(i * 7 + i // 10) % len(hospitals)]
        doctor = doctors[(i * 5) % len(doctors)]
        amount = int(base * (0.92 + (i % 5) * 0.035))
        uhid = f"SIM-{city[:2].upper()}-{3100+i:04d}"
        story_forms = [
            f"Our family is raising funds for {person}, who is receiving care for {condition} at {hospital} in {city}. {doctor} provided a dated hospital estimate for {treatment}; the requested ₹{amount:,} covers the listed procedure, medicines, and follow-up visits. The patient UHID is {uhid}. We have attached the estimate and the latest clinic report, and can confirm the bill directly with the hospital.",
            f"After tests at {hospital}, {doctor} diagnosed {person} with {condition}. The treatment plan is {treatment}. We request ₹{amount:,} for the cost items in the hospital quotation dated 12 August 2025. Admission reference {uhid}; the attached report and estimate show the same patient and facility in {city}. Donations will be used for this treatment and unused funds returned.",
            f"{person} is under {doctor}'s care at {hospital}, {city}, for {condition}. The hospital's written estimate for {treatment} is ₹{amount:,}, itemized across procedure, bed, and prescribed medicines. The patient number is {uhid}; a recent diagnostic report and billing desk quotation are attached. Our family is contributing what we can and will provide receipts after each payment.",
        ]
        story = story_forms[i % 3]
        docs = [
            ("HOSPITAL_ESTIMATE", f"Synthetic estimate {uhid}", f"[Page 1] {hospital} estimate letter. Patient {person}. UHID {uhid}. Diagnosis: {condition}. Plan: {treatment}. Estimated total ₹{amount:,}. Prepared by {doctor}; dated 12 August 2025. Itemized hospital charges and follow-up medicines."),
            ("MEDICAL_REPORT", f"Synthetic clinic report {uhid}", f"[Page 1] Clinic report for {person} at {hospital}, {city}. Findings support diagnosis of {condition}; {doctor} recommends {treatment}. Patient reference {uhid}.")
        ]
        add(rows, "legitimate", "MEDICAL", "legitimate_medical", f"Care support for {person}: {condition}", story, amount, docs, person, "FAMILY", city, state)

    fraud_patterns = [
        ("Friends, send the contribution to my personal account first and I will settle the hospital later. The online appeal has no hospital bill yet.", "PERSONAL_PAYOUT"),
        ("To release the treatment grant, supporters must pay a small verification charge through a gift card or crypto wallet. Do not wait for platform review.", "ADVANCE_FEE"),
        ("The patient has a secret cure with a guaranteed recovery in days, and the family asks everyone to fund it before speaking to any clinician.", "MIRACLE_CURE"),
        ("The fundraiser organizer admits the hospital estimate was altered to increase donations; the original bill is unavailable for comparison.", "FORGED_RECORD"),
        ("A prize claim will cover the operation once donors pay the release charge. The request uses lottery winnings as proof and gives no clinical paperwork.", "PRIZE_SCAM"),
        ("Contributions are requested by international transfer outside the platform. No treating facility, diagnosis record, or named clinician is supplied.", "UNTRACEABLE_PAYMENT"),
    ]
    fraud_titles = ["Emergency operation appeal", "Urgent care fundraiser", "Treatment support request", "Critical patient appeal", "Medical rescue collection"]
    for i in range(60):
        city, state = cities[(i * 7 + (i // 30) + 2) % len(cities)]
        person = people[(i * 3 + 4) % len(people)]
        amount = [1800000, 7200000, 450000, 3200000, 9500000, 1250000][i % 6]
        pattern, subtype = fraud_patterns[i % len(fraud_patterns)]
        details = f"The story claims {person} needs an urgent procedure in {city}, but provides no independently checkable admission reference. Goal ₹{amount:,}. {pattern}"
        if i % 4 == 0:
            details += f" The organizer names {hospitals[i % len(hospitals)]} and says a doctor will confirm later, but no dated estimate or patient number is attached."
        docs = []
        if i % 5 == 0:
            docs = [("HOSPITAL_ESTIMATE", "Unverified estimate image transcript", f"[Page 1] Unverified draft for patient {person}; no UHID or provider signature. Claimed total ₹{amount:,}. Facility contact and billing details absent.")]
        add(rows, "fraudulent", "MEDICAL", f"fraud_medical_{subtype.lower()}", f"{fraud_titles[i % len(fraud_titles)]} for {person}", details, amount, docs, person, "FAMILY", city, state)

    borderline_specs = [
        ("MEDICAL", "incomplete_medical", "A family appeal for recurring infusion costs", "A relative is receiving infusions in Jaipur. We are collecting ₹260,000 for the next phase, but the clinic estimate is still pending and the patient number was not included. The family can share records after admission.", 260000, "Jaipur", "Rajasthan"),
        ("MEDICAL", "inconsistent_medical", "Help with a planned cardiac procedure", "The story describes a valve procedure and a Chennai specialist, while the uploaded note only mentions diagnostic tests. The ₹1,100,000 goal includes travel and recovery costs but no itemized split.", 1100000, "Chennai", "Tamil Nadu"),
        ("MEDICAL", "third_party_medical", "Support for a neighbour's recovery", "We are raising ₹175,000 for a neighbour after a serious injury. The family has asked us to keep their identity private. A discharge note is mentioned, but no document is attached.", 175000, "Kochi", "Kerala"),
        ("MEDICAL", "elevated_cost_medical", "Assistance for a complex neurological treatment", "The patient is being assessed at a private hospital in Pune. The campaign asks ₹4,800,000 for a multi-stage neurological treatment, but the written estimate is one page and does not describe the stages or clinician.", 4800000, "Pune", "Maharashtra"),
        ("COMMUNITY", "borderline_relief", "Temporary help after a building fire", "Several tenants lost belongings in a building fire in Ahmedabad. The organizer requests ₹640,000 for temporary housing and supplies. A local association has confirmed the incident, but itemized receipts are not available yet.", 640000, "Ahmedabad", "Gujarat"),
        ("EDUCATION", "borderline_education", "Tuition help before semester registration", "A student says the semester invoice is due next week and seeks ₹390,000. The college is named, but the invoice appears to be for a full year and the student number is missing.", 390000, "Bengaluru", "Karnataka"),
        ("MEDICAL", "borderline_medical", "Help with post-surgery rehabilitation", "The family requests ₹310,000 for rehabilitation following surgery in Lucknow. A discharge note supports the operation, but the current treatment plan and facility quotation have not been provided.", 310000, "Lucknow", "Uttar Pradesh"),
        ("MEDICAL", "borderline_medical", "Care fund for a patient outside the city", "A family friend is collecting ₹520,000 for a patient in Delhi. The story includes a diagnosis and doctor name but no relationship authorization or hospital cost breakdown.", 520000, "Delhi", "Delhi"),
    ]
    for i in range(40):
        category, subtype, title, story, amount, city, state = borderline_specs[i % len(borderline_specs)]
        name = people[(i + 1) % len(people)]
        nuances = [
            "A dated billing confirmation has not arrived yet.",
            "The organizer only has a relative's verbal summary so far.",
            "The family has not authorized the provider to confirm the details.",
            "The amount combines separate expenses without individual receipts.",
            "The next document review is expected after the upcoming appointment.",
        ]
        story += f" {nuances[i % len(nuances)]} Review note BR-{i + 1:02d}."
        docs = []
        if i % 4 == 0:
            docs = [("OTHER", "Partial supporting note", f"[Page 1] Partial note naming {name} and {city}; does not include a complete estimate, admission ID, or itemized treatment plan. Review note BR-{i + 1:02d}.")]
        add(rows, "borderline", category, subtype, f"{title} — {name}", story, amount, docs, name, "FAMILY", city, state)

    edu_legit = [
        ("EDUCATION", "tuition", "semester tuition", 148000, "Pune", "Maharashtra"),
        ("EDUCATION", "school_fee", "school fees and books", 72000, "Jaipur", "Rajasthan"),
        ("COMMUNITY", "flood_relief", "household repair after flooding", 210000, "Kochi", "Kerala"),
        ("COMMUNITY", "fire_relief", "temporary shelter and supplies after a fire", 260000, "Ahmedabad", "Gujarat"),
        ("EDUCATION", "hostel", "hostel and lab fees", 195000, "Chennai", "Tamil Nadu"),
    ]
    for i in range(20):
        category, kind, need, amount, city, state = edu_legit[i % len(edu_legit)]
        person = people[(i * 2 + 3) % len(people)]
        institution = ["Deccan Institute of Design", "Coastal State Polytechnic", "Sahyadri Public School", "Riverbend Residents Association", "Old City Ward Committee"][i % 5]
        reference = f"{kind.upper()}-{i + 1:03d}"
        story = f"{person} is seeking ₹{amount:,} for {need} through {institution} in {city}. The attached official fee notice or association minutes identify the intended recipients and spending period. The organizer will pay the institution or vendors directly and post receipts; the request does not include personal cash expenses. The committee record is {reference}."
        doc = ("FEE_STRUCTURE" if category == "EDUCATION" else "COMMUNITY_RECORD", f"Synthetic {kind} record", f"[Page 1] {institution}, {city}, confirms {person}'s {need}. Approved amount ₹{amount:,}. Date: 18 July 2025. Payment recipient and purpose are itemized in the attached notice. Record {reference}.")
        add(rows, "legitimate", category, f"legitimate_{kind}", f"Verified support for {person}: {need}", story, amount, [doc], person, "SELF", city, state)

    fraud_edu = [
        ("EDUCATION", "scholarship_fee", "Scholarship release payment", "A student is promised a large scholarship but must pay an upfront release charge to a private account. No college admission or award letter is supplied."),
        ("EDUCATION", "fake_enrollment", "Urgent college seat reservation", "The organizer claims a guaranteed university seat for several students if donors pay a reservation charge today. The institution cannot be contacted and there is no fee notice."),
        ("COMMUNITY", "relief_collection", "Disaster relief collection", "Funds are requested for a relief camp, but the organizer gives no affected locality or recipient list and asks for contributions through an unmonitored transfer channel."),
        ("EDUCATION", "prize_scam", "Education grant prize claim", "A family has supposedly won an education grant prize and asks supporters to pay a processing fee before the school funds are released. No student or school record is named."),
        ("COMMUNITY", "forged_receipts", "Community repair appeal", "The organizer says the building invoices were edited to show a larger repair total. Residents have not confirmed the project and vendor estimates are missing."),
    ]
    for i in range(20):
        category, subtype, title, story = fraud_edu[i % len(fraud_edu)]
        city, state = cities[(i * 2 + 5) % len(cities)]
        person = people[(i + 6) % len(people)]
        amount = [95000, 420000, 680000, 155000, 830000][i % 5]
        story = f"{story} The appeal says it is for {person} in {city} and requests ₹{amount:,}. No independently verifiable admission, association authorization, invoice, or recipient list is attached."
        if i % 3 == 0:
            story += " The organizer says to claim the reward after sending money, without asking questions."
        story += f" Appeal reference EDU-{i + 1:03d}."
        add(rows, "fraudulent", category, subtype, f"{title}: {person}", story, amount, (), person, "SELF", city, state)

    assert len(rows) == 200, len(rows)
    assert len({row["input"]["story"] for row in rows}) == 200, "Scenario narratives must be distinct"
    counts = {}
    for row in rows:
        key = (row["ground_truth"], row["input"]["category"])
        counts[key] = counts.get(key, 0) + 1
    assert counts[("legitimate", "MEDICAL")] == 60
    assert counts[("fraudulent", "MEDICAL")] == 60
    assert counts[("borderline", "MEDICAL")] == 30
    assert counts[("borderline", "EDUCATION")] == 5
    assert counts[("borderline", "COMMUNITY")] == 5
    assert sum(1 for r in rows if r["ground_truth"] == "legitimate" and r["input"]["category"] in {"EDUCATION", "COMMUNITY"}) == 20
    assert sum(1 for r in rows if r["ground_truth"] == "fraudulent" and r["input"]["category"] in {"EDUCATION", "COMMUNITY"}) == 20
    return rows


if __name__ == "__main__":
    cases = build()
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cases), encoding="utf-8")
    print(f"Wrote {len(cases)} synthetic cases to {OUT}")
