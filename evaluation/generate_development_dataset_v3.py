"""Generate the grouped, synthetic V3 development corpus (not a final test set).

Scenario families are split as whole groups between development and validation.
The generator is deterministic; all labels are authored from the stated scenario
facts before running either verifier. No previous benchmark rows are read.
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name("development_scenarios_v3.jsonl")
NAMES = ["Mira Shah", "Devika Nair", "Ishan Kulkarni", "Farah Basu", "Neelam Rao",
         "Arun Thomas", "Kavita Menon", "Zoya Qureshi", "Ritu Sen", "Adil D'Souza"]
PLACES = ["Nashik", "Udupi", "Jorhat", "Satara", "Dindigul", "Kohima", "Hassan", "Balasore", "Bundi", "Siliguri"]
CLASSES = ("legitimate", "fraudulent", "borderline")


def money(value):
    return f"₹{value:,}"


def doc(doc_type, title, content):
    return {"doc_type": doc_type, "title": title, "content": content}


def case_payload(category, label, family, source, i):
    person, place = NAMES[i], PLACES[(i + 2) % len(PLACES)]
    amount = 68000 + (i * 3700)
    ident = f"SF-{(i + 1) * 139:05d}"
    # Every record predates the shared 16-Nov-2026 submission date.
    date = f"{10 + i:02d} October 2026"
    if category == "MEDICAL":
        beneficiary_type = "SELF"
        if label == "legitimate":
            if family == "home_cardiac_monitoring":
                title = f"Cardiac monitoring support for {person}"
                story = (f"{person} is recovering from a complex cardiac procedure and needs a home monitoring unit. "
                         f"The {source} provided a signed estimate for {money(amount)}; the request covers the documented device and setup.")
                documents = [doc("HOSPITAL_ESTIMATE", "Cardiac equipment estimate",
                                 f"{source}\nPatient Name: {person}\nEstimate ref: {ident}\nDate: {date}\n"
                                 f"Treatment estimate for home cardiac monitoring: {money(amount)}\nConsultant: Dr Saira Paul"),
                             doc("CLINICAL_NOTE", "Cardiology follow-up note",
                                 f"{source}\nName: {person}\nThe cardiac team recommends home rhythm monitoring after discharge. "
                                 "A portable device and setup visits are part of the recovery plan.")]
            else:
                title = f"Extended rehabilitation travel for {person}"
                story = (f"{person} has a documented neurological injury and must attend repeated rehabilitation sessions. "
                         f"The {source} lists the treatment and transport plan; the unusually high goal includes the remote route and overnight stays.")
                documents = [doc("REHAB_PLAN", "Therapy and travel plan",
                                 f"{source}\nPatient: {person}\nClinical plan ref {ident}, dated {date}. "
                                 "The patient requires an extended course of mobility therapy. Because the clinic is distant, "
                                 f"accessible transport and overnight accommodation are included. Total approved estimate: {money(amount)}."),
                             doc("PATIENT_RECORD", "Discharge and mobility record",
                                 f"{source}\nPatient Name: {person}\nDischarge summary {ident}. "
                                 "Neurology review records limited mobility and recommends supervised rehabilitation.")]
        elif label == "fraudulent":
            if family == "beneficiary_record_divergence":
                other = NAMES[(i + 4) % len(NAMES)]
                title = f"Surgery account support for {person}"
                story = (f"The appeal is for {person}'s scheduled procedure at {source}. The family says the patient number is {ident}. "
                         "A fresh estimate is requested because the admission is imminent.")
                documents = [doc("HOSPITAL_ESTIMATE", "Admission estimate",
                                 f"{source}\nPatient Name: {other}\nPatient file: SF-{(i + 4) * 139 + 139:05d}\n"
                                 f"Date: {date}\nEstimate for the planned procedure: {money(amount)}\nPrepared by the admissions office.")]
            elif family == "coherent_but_fabricated_dossier":
                title = f"Specialist follow-up package for {person}"
                story = (f"{person} is receiving follow-up care at {source}; the family seeks {money(amount)} for the listed treatment and monitoring schedule. "
                         "The clinic estimate and patient summary agree on the need and requested amount.")
                documents = [doc("SPECIALIST_ESTIMATE", "Follow-up cost schedule",
                                 f"{source}\nPatient: {person}\nEstimate {ident}, dated {date}. "
                                 f"Monitoring and treatment package total: {money(amount)}. Consultant: Dr Meera Bose."),
                             doc("CLINICAL_SUMMARY", "Outpatient specialist summary",
                                 f"{source}\nName: {person}\nRecord {ident}. Follow-up care and monitoring are recommended. "
                                 "The outpatient team scheduled the next review.")]
            else:
                title = f"Unpaid post-operative balance for {person}"
                story = (f"{person} needs donor help for an unpaid balance of {money(amount)} at {source}. "
                         "The hospital has not received funds and the patient account remains open.")
                documents = [doc("FINAL_RECEIPT", "Account settlement record",
                                 f"{source}\nPatient: {person}\nRecord {ident}, dated {date}. "
                                 f"The amount of {money(amount)} was received and credited in full. "
                                 "The account is settled; no further payment is due.")]
        else:
            if family == "preauthorization_waiting":
                title = f"Provisional oncology plan for {person}"
                story = (f"{person} has been referred to {source}; the family is seeking {money(amount)} for a proposed course. "
                         "The clinic says final scheduling depends on a review board decision.")
                documents = [doc("PROVISIONAL_PLAN", "Unsigned treatment proposal",
                                 f"{source}\nPatient name: {person}\nDraft plan {ident}, dated {date}. "
                                 f"Indicative treatment estimate: {money(amount)}. The plan is provisional and not yet approved.")]
            else:
                title = f"Home-care supplies for {person}"
                story = (f"A local volunteer group is collecting {money(amount)} for care supplies said to be needed by {person}. "
                         "No clinic or named practitioner is included in the papers currently available.")
                documents = [doc("COMMUNITY_NOTE", "Volunteer collection note",
                                 f"{place} residents' committee recorded a request for home-care assistance on {date}. "
                                 "The note does not identify a patient record, treating service or item list.")]
        return {"title": title, "category": category, "story": story, "goal_amount": amount,
                "goal_currency": "INR", "beneficiary_name": person, "beneficiary_type": beneficiary_type,
                "city": place, "state": "India", "submitted_on": "2026-11-16", "documents": documents}

    if category == "EDUCATION":
        beneficiary_type = "SELF"
        if label == "legitimate":
            if family == "access_design_practicum":
                title = f"Accessible design practicum for {person}"
                story = (f"{person} is enrolled in a tactile-interface practicum at {source}. The workshop materials and bench time cost {money(amount)}, "
                         "as itemised by the registrar. The request is for the current semester only.")
                documents = [doc("FEE_STATEMENT", "Registrar's workshop fee statement",
                                 f"{source}\nStudent: {person}\nEnrollment ref {ident}; dated {date}. "
                                 f"Current practicum fees and accessible equipment use: {money(amount)}. Fee is due this semester."),
                             doc("ENROLMENT_RECORD", "Current course record",
                                 f"{source}\nStudent name: {person}\nThe learner is enrolled in the accessible design workshop this term. "
                                 "The course coordinator confirms active attendance.")]
            else:
                title = f"Marine instrumentation apprenticeship for {person}"
                story = (f"{person} has an apprenticeship place at {source}; the attached payment schedule includes safety equipment, "
                         f"ferry travel, and a residential block costing {money(amount)}.")
                documents = [doc("APPRENTICE_LEDGER", "Training office account extract",
                                 f"{source}\nCandidate: {person}\nApprentice number {ident}, dated {date}. "
                                 f"Residential block, safety kit and transport fees due: {money(amount)}."),
                             doc("COURSE_RECORD", "Training appointment record",
                                 f"{source}\nCandidate: {person}\nThe marine instrumentation apprenticeship is active. "
                                 "The schedule includes workshop, vessel safety and field placement modules.")]
        elif label == "fraudulent":
            if family == "teaching_period_mismatch":
                title = f"Extended language certificate for {person}"
                story = (f"{person}'s request covers twelve months of language instruction at {source}; the goal is {money(amount)} "
                         "for the full academic year.")
                documents = [doc("COURSE_CALENDAR", "Institute's published session calendar",
                                 f"{source}\nCandidate: {person}\nThe certificate track has ten instructional weeks. "
                                 "No additional teaching block is scheduled after this intake.")]
            elif family == "book_bundle_count_mismatch":
                title = f"Textbook bundle for {person}'s study circle"
                story = (f"{person} coordinates a request for 42 book sets for the {source} satellite classroom. "
                         "The campaign covers a new full distribution, not a replacement order.")
                documents = [doc("DELIVERY_REGISTER", "School receiving register",
                                 f"{source}\nDelivery batch {ident}, dated {date}. The logged consignment contains 26 book sets; "
                                 "each set was signed for by the classroom custodian.")]
            else:
                title = f"Studio access and material allowance for {person}"
                story = (f"{person} is enrolled at {source}. The campaign seeks {money(amount)} for an equipment allowance and supervised studio access listed by the school.")
                documents = [doc("CURRENT_ENROLMENT", "Student services record",
                                 f"{source}\nStudent: {person}\nActive enrollment reference {ident}, dated {date}. "
                                 "The student has a current place in the applied arts program."),
                             doc("STUDENT_ACCOUNT", "Allowance and studio account",
                                 f"{source}\nStudent: {person}\nAccount {ident}, dated {date}. "
                                 f"Equipment allowance and supervised studio access total {money(amount)}. The amount is due this term.")]
        else:
            if family == "conditional_lab_seat":
                title = f"Conditional laboratory place for {person}"
                story = (f"{person} has been offered a place at {source}, but the lab seat remains conditional on an entrance assessment. "
                         f"The family is asking for {money(amount)} before the final decision.")
                documents = [doc("CONDITIONAL_OFFER", "Admissions portal printout",
                                 f"{source}\nApplicant: {person}\nOffer ref {ident}, dated {date}. "
                                 "A place is reserved pending assessment; enrollment is not confirmed.")]
            else:
                title = f"Term payment pending sponsorship for {person}"
                story = (f"{person} studies at {source}. A family sponsor may cover part of a {money(amount)} term bill, "
                         "but the sponsor has not answered the school yet.")
                documents = [doc("ACCOUNT_SNAPSHOT", "Unstamped account summary",
                                 f"{source}\nStudent: {person}\nA balance is shown for the current term, but the image lacks a date and the sponsor credit is unresolved.")]
        return {"title": title, "category": category, "story": story, "goal_amount": amount,
                "goal_currency": "INR", "beneficiary_name": person, "beneficiary_type": beneficiary_type,
                "city": place, "state": "India", "submitted_on": "2026-11-16", "documents": documents}

    # COMMUNITY
    organisation = f"{place} Neighbourhood Works Collective"
    if label == "legitimate":
        if family == "tidal_pump_retrofit":
            title = f"Tidal pump retrofit for the {place} ward"
            story = (f"The {organisation} has a signed ward resolution to replace a corroded pump-control cabinet. "
                     f"A marine electrician's estimate for the salt-resistant unit and installation is {money(amount)}.")
            documents = [doc("ENGINEERING_QUOTE", "Electrical contractor's work schedule",
                             f"{source}\nClient: {organisation}\nQuote {ident}, dated {date}. "
                             f"Salt-rated motor controls, wiring and installation total {money(amount)}."),
                         doc("WARD_RESOLUTION", "Ward works committee decision",
                             f"{organisation}\nMeeting record {ident}. Members approved replacement of the pump-control cabinet and delegated supervision to the ward engineer.")]
        else:
            title = f"Mobile reading cart for the {place} market"
            story = (f"The {organisation} will move a weatherproof book cart between three market streets after school hours. "
                     f"The local fabricator's quote for cart, awning and lockable shelves is {money(amount)}.")
            documents = [doc("FABRICATOR_QUOTE", "Workshop costing sheet",
                             f"{source}\nClient: {organisation}\nJob card {ident}, dated {date}. "
                             f"Lockable mobile cart, awning and shelves are priced at {money(amount)}."),
                         doc("COLLECTIVE_MINUTES", "Community meeting extract",
                             f"{organisation}\nThe market association approved the reading cart route and named a volunteer custodian. "
                             "The proposal limits collection hours to the after-school period.")]
    elif label == "fraudulent":
        if family == "vendor_beneficiary_count":
            title = f"Rainwater cisterns for 38 homes in {place}"
            story = (f"The collective asks donors to finance 38 household cisterns across {place}. "
                     f"The procurement request lists {money(amount)} and expects every listed household to receive one unit.")
            documents = [doc("PROCUREMENT_LOG", "Supplier dispatch count",
                             f"{source}\nDelivery record {ident}, dated {date}. The dispatch contains 19 household cisterns, "
                             "delivered to the collective store; no second shipment is listed.")]
        elif family == "internally_aligned_false_project":
            title = f"Shared repair workshop for {place} residents"
            story = (f"The collective proposes a staffed repair workshop in {place}; a vendor schedule from {source} sets the requested total at {money(amount)}.")
            documents = [doc("COMMITTEE_RESOLUTION", "Community committee resolution",
                             f"{organisation}\nResolution {ident}, dated {date}. Members approved a shared neighborhood repair workshop and named an equipment custodian."),
                         doc("VENDOR_ESTIMATE", "Workshop equipment estimate",
                             f"{source}\nClient: {organisation}\nEstimate {ident}, {date}. "
                             f"Benches, hand tools and safety equipment for the repair workshop total {money(amount)}.")]
        else:
            title = f"Community kitchen fuel advance in {place}"
            story = (f"The collective requests {money(amount)} for an unpaid commercial-kitchen fuel balance. "
                     "Its coordinator says the supplier is still awaiting payment.")
            documents = [doc("SUPPLIER_RECEIPT", "Fuel account closure",
                             f"{source}\nAccount {ident}, dated {date}. The collective's complete fuel balance was paid and closed; "
                             "the supplier records no outstanding amount.")]
    else:
        if family == "shoreline_permit_pending":
            title = f"Raised walkway at the {place} landing"
            story = (f"Residents propose a short raised walkway to reach the ferry landing during spring tides. "
                     f"The request is {money(amount)}, but the public-works consent has not been issued.")
            documents = [doc("DRAFT_SITE_NOTE", "Engineering visit note",
                             f"{source}\nDraft note {ident}, dated {date}. The route is under review; permission from the shoreline authority is pending.")]
        else:
            title = f"Heat shelter at the {place} bus interchange"
            story = (f"The collective is considering a shaded rest point for outdoor workers. "
                     "A volunteer sketch exists, but there is no site consent or signed estimate yet.")
            documents = [doc("VOLUNTEER_SKETCH", "Unendorsed shelter sketch",
                             f"{organisation}\nA draft layout was discussed at an informal meeting. No location, approved bill of quantities, or municipal consent is recorded.")]
    return {"title": title, "category": category, "story": story, "goal_amount": amount,
            "goal_currency": "INR", "beneficiary_name": organisation, "beneficiary_type": "ORGANISATION",
            "city": place, "state": "India", "submitted_on": "2026-11-16", "documents": documents}


GROUPS = {
    "MEDICAL": {
        "legitimate": [("home_cardiac_monitoring", "Coastal Cardiac Centre"), ("remote_neurology_rehab", "Kaveri Neuro Clinic")],
        "fraudulent": [("beneficiary_record_divergence", "Meadow Regional Hospital"), ("coherent_but_fabricated_dossier", "North Valley Hospital")],
        "borderline": [("preauthorization_waiting", "Narmada Oncology Unit"), ("care_supply_request_unlinked", "District Care Centre")],
    },
    "EDUCATION": {
        "legitimate": [("access_design_practicum", "Konkan Technical Institute"), ("marine_apprentice_block", "Bayline Training College")],
        "fraudulent": [("teaching_period_mismatch", "Sundar Language Academy"), ("internally_consistent_enrollment_and_invoice", "Eastern Learning Cooperative")],
        "borderline": [("conditional_lab_seat", "Aranya Science College"), ("sponsor_credit_uncertain", "Swaraj Arts Institute")],
    },
    "COMMUNITY": {
        "legitimate": [("tidal_pump_retrofit", "Regional Waterworks Office"), ("mobile_market_reading_cart", "District Craft Workshop")],
        "fraudulent": [("vendor_beneficiary_count", "Rainfield Cistern Supply"), ("internally_aligned_false_project", "Common Table Fuels")],
        "borderline": [("shoreline_permit_pending", "Coastal Engineering Circle"), ("informal_heat_shelter", "Ward Volunteer Forum")],
    },
}


def generate():
    rows, serial = [], 1
    for category, labels in GROUPS.items():
        for label in CLASSES:
            for family_no, (family, source) in enumerate(labels[label]):
                split = "development" if family_no == 0 else "validation"
                for variant in range(10):
                    input_data = case_payload(category, label, family, source, variant)
                    rows.append({
                        "case_id": f"V3D-{serial:03d}", "ground_truth": label,
                        "scenario_family": family, "document_source": source,
                        "split": split, "variant": variant + 1, "synthetic": True,
                        "label_basis": ("Author knows the displayed medical records have fabricated provenance; the dossier is internally consistent and contains no detectable authenticity signal."
                                        if family == "coherent_but_fabricated_dossier" else
                                        "Author knows the displayed education records have fabricated provenance; the dossier is internally consistent and contains no detectable authenticity signal."
                                        if family == "internally_consistent_enrollment_and_invoice" else
                                        "Author knows the displayed community records have fabricated provenance; the dossier is internally consistent and contains no detectable authenticity signal."
                                        if family == "internally_aligned_false_project" else
                                        "Authored scenario facts; labels set before verifier execution."),
                        "expected_action": {"legitimate": "APPROVED", "fraudulent": "FLAG_FOR_REVIEW",
                                            "borderline": "NEEDS_MORE_INFORMATION"}[label],
                        "input": input_data,
                    })
                    serial += 1
    if len(rows) != 180:
        raise AssertionError(f"Expected 180 scenarios; generated {len(rows)}")
    return rows


if __name__ == "__main__":
    rows = generate()
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"wrote {len(rows)} synthetic cases to {OUT}")
