"""Author a separate 300-case synthetic final set after the V3 freeze.

This script has no dependency on development datasets and does not load a
verifier. Execute it only after writing `final_test_protocol_v3.md` and the
V3 freeze manifest. Labels are assigned by the authored family specification.
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name("final_test_scenarios_v3.jsonl")
PEOPLE = ["Nila Fernandes", "Rahul Bedi", "Tara Mukherjee", "Omar Jacob", "Sonal Dutta",
          "Kabir Pradhan", "Madhavi Pillai", "Javed Ansari", "Lina Mathew", "Rohan Barman"]
TOWNS = ["Karwar", "Pithoragarh", "Thanjavur", "Dausa", "Imphal", "Vapi", "Chitradurga", "Puri", "Kottayam", "Tinsukia"]

# 30 families, wholly distinct from V3 development families. Counts per
# category are 100; aggregate labels are exactly 100 legitimate, 100 fraudulent,
# and 100 borderline. Family labels were set before running either verifier.
FAMILIES = {
    "MEDICAL": [
        ("legitimate", "enzyme_cold_chain", "Western Ghats Metabolic Institute", "medical_supported"),
        ("legitimate", "home_ventilation_backup", "Central Respiratory Centre", "medical_equipment"),
        ("legitimate", "island_burn_recovery", "Bay District Rehabilitation Service", "medical_travel"),
        ("legitimate", "orthotic_refitting", "Ananta Mobility Clinic", "medical_supported"),
        ("fraudulent", "patient_and_record_crossing", "Lotus Bay Infirmary", "medical_identity_conflict"),
        ("fraudulent", "unrelated_account_recipient", "Children's North Pavilion", "medical_third_party_payee"),
        ("fraudulent", "internally_consistent_but_forged_clinic_file", "Cedar Ridge Specialty Hospital", "consistent_fabrication"),
        ("borderline", "trial_slot_authorization_pending", "Newbridge Clinical Unit", "medical_provisional"),
        ("borderline", "family_cost_share_unclear", "Riverbend Oncology Centre", "medical_shared_cost"),
        ("borderline", "patient_link_not_in_extract", "Kalyan Sleep Laboratory", "medical_missing_identity"),
    ],
    "EDUCATION": [
        ("legitimate", "accessible_exam_studio", "Mosaic Examination Board", "education_supported"),
        ("legitimate", "field_research_recordings", "Peninsula Marine College", "education_research"),
        ("legitimate", "archival_language_keyboard", "Deccan Translation School", "education_supported"),
        ("fraudulent", "credential_calendar_shortfall", "Atria Professional Academy", "education_duration"),
        ("fraudulent", "paid_term_balance_reused", "Southbank Applied Arts College", "education_settled"),
        ("fraudulent", "equipment_dispatch_shortfall", "Blue Courtyard Learning Lab", "education_quantity"),
        ("fraudulent", "consistent_bursary_papers_forged", "Saffron Vale Institute", "consistent_fabrication"),
        ("borderline", "seat_held_until_practical", "Meridian Aviation School", "education_conditional"),
        ("borderline", "grant_installment_unposted", "Triveni School of Design", "education_sponsor_pending"),
        ("borderline", "account_image_without_issue_date", "North Loop Technical College", "education_undated"),
    ],
    "COMMUNITY": [
        ("legitimate", "market_food_cooling_room", "Harbour Cooperative Works Office", "community_supported"),
        ("legitimate", "earthquake_masonry_repair", "Upper Valley Resilience Council", "community_supported"),
        ("legitimate", "compost_route_cold_store", "Greenlane Producers Forum", "community_supported"),
        ("fraudulent", "dispatch_quantity_diverges", "Delta Modular Fabrication", "community_quantity"),
        ("fraudulent", "supplier_ledger_closed", "Crown Road Building Supply", "community_settled"),
        ("fraudulent", "false_provenance_project_alignment", "Mango Tree Civic Foundation", "consistent_fabrication"),
        ("borderline", "coastal_access_permit_unissued", "Estuary Planning Desk", "community_permit_pending"),
        ("borderline", "partner_share_not_confirmed", "Kora Valley Housing Partnership", "community_cost_share"),
        ("borderline", "committee_minutes_unratified", "East Ward Assembly Secretariat", "community_draft"),
        ("borderline", "supplier_quote_expires_soon", "Metro Fringe Food Exchange", "community_quote_pending"),
    ],
}


def m(amount):
    return f"₹{amount:,}"


def document(kind, title, text):
    return {"doc_type": kind, "title": title, "content": text}


def build_input(category, label, family, source, mode, index):
    person = PEOPLE[index]
    place = TOWNS[(index + 3) % len(TOWNS)]
    org = f"{place} Shared Services Association"
    amount = 145000 + index * 28750
    ref = f"QX-{index + 31:04d}"
    day = 4 + index
    date = f"{day:02d} September 2026"
    beneficiary = person if category != "COMMUNITY" else org
    btype = "SELF" if category != "COMMUNITY" else "ORGANISATION"
    docs = []

    if mode == "medical_supported" and family == "enzyme_cold_chain":
        title = f"Specialist follow-up plan for {person}"
        story = (f"{person} is being treated at {source} for a rare enzyme-processing disorder. The quarterly cold-chain dose and home nursing are itemised at {m(amount)}. "
                 "The requested amount covers the next clinical interval; travel is separate and not included.")
        docs = [document("SPECIALIST_ESTIMATE", "Quarterly medication and nursing schedule",
                         f"{source}\nPatient: {person}\nSchedule ref {ref}, dated {date}. "
                         f"Cold-chain medication and home nursing for the next interval total {m(amount)}. "
                         "Consultant: Dr Isha Lal."),
                document("CARE_PLAN", "Metabolic team care plan",
                         f"{source}\nName: {person}\nThe consultant plan continues quarterly enzyme replacement with nurse supervision. "
                         "The cold-chain schedule is attached to the patient file.")]
    elif mode == "medical_supported" and family == "orthotic_refitting":
        title = f"Replacement gait orthosis for {person}"
        story = (f"{person} has outgrown a custom gait orthosis following a spinal injury. {source} recorded a new fitting plan, "
                 f"including pressure mapping and home adjustment visits, at {m(amount)}.")
        docs = [document("ORTHOTIC_FITTING_PLAN", "Mobility fitting work order",
                         f"{source}\nPatient: {person}\nFitting order {ref}; {date}. "
                         f"Custom gait orthosis, pressure mapping and home adjustments: total {m(amount)}."),
                document("REHAB_REVIEW", "Rehabilitation service note",
                         f"{source}\nName: {person}\nThe mobility team recommends a replacement device after the patient's growth-related fit change.")]
    elif mode == "medical_equipment":
        title = f"Home airway system for {person}"
        story = (f"A respiratory specialist has prescribed a backup ventilation unit for {person}. The family lives on an unreliable feeder line; "
                 f"the hospital's equipment schedule includes power switching and service visits at {m(amount)}.")
        docs = [document("RESPIRATORY_EQUIPMENT_PLAN", "Home device and service schedule",
                         f"{source}\nPatient name: {person}\nEquipment order {ref}; {date}. "
                         f"Ventilator, battery switching module, installation and two service visits: total {m(amount)}. "
                         "Respiratory consultant signed the plan."),
                document("DISCHARGE_NOTE", "Discharge equipment recommendation",
                         f"{source}\nPatient: {person}\nThe home airway setup is recommended at discharge. "
                         "A power interruption log was reviewed by the respiratory service.")]
    elif mode == "medical_travel":
        title = f"Burn recovery travel and lodging for {person}"
        story = (f"{person} needs repeated scar-management sessions at {source}, which is across a water crossing from home. "
                 f"The goal of {m(amount)} includes return transport and accessible overnight lodging alongside the hospital course.")
        docs = [document("REHAB_SCHEDULE", "Rehabilitation attendance plan",
                         f"{source}\nPatient: {person}\nCare schedule {ref}, {date}. "
                         "Scar-management and mobility sessions are arranged across multiple visits. "
                         f"The travel desk's combined treatment and transport estimate is {m(amount)}."),
                document("TRAVEL_DESK_QUOTE", "Access route and lodging quote",
                         f"{source} patient access desk\nFor: {person}\nReturn crossing, wheelchair vehicle and lodging estimate {m(amount)}. "
                         "The route requires an overnight stay between sessions.")]
    elif mode == "medical_identity_conflict":
        title = f"Medication release for {person}"
        other = PEOPLE[(index + 5) % len(PEOPLE)]
        story = f"{person} is due to receive a specialist medication package from {source}; the patient file is {ref}. Funds are requested for the next release."
        docs = [document("CLINIC_DISCHARGE", "Specialist discharge record",
                         f"{source}\nPatient: {person}\nClinic file {ref}. The discharge plan calls for a supervised follow-up."),
                document("PHARMACY_DEBIT_NOTE", "Pharmacy ledger copy",
                         f"{source} outpatient pharmacy\nPatient: {other}\nFile: HX-{index + 91:04d}. "
                         f"Medication package and release fee: {m(amount)}. Prepared {date}.")]
    elif mode == "medical_settled":
        title = f"Unpaid newborn care charge for {person}"
        story = f"The family is trying to clear an outstanding neonatal bill of {m(amount)} at {source}; no one has made a payment."
        docs = [document("BILLING_LEDGER", "Neonatal account closeout",
                         f"{source}\nAccount {ref}; {date}. Patient: {person}. "
                         f"Payment of {m(amount)} posted in full. The account has zero balance and is closed.")]
    elif mode == "medical_third_party_payee":
        title = f"Infusion account for {person}"
        story = f"{person} needs the infusion cost covered at {source}; the invoice is current and the requested sum is {m(amount)}."
        docs = [document("INFUSION_INVOICE", "Current outpatient invoice",
                         f"{source}\nPatient: {person}\nInvoice {ref}, {date}. Infusion and monitoring cost: {m(amount)}."),
                document("PAYMENT_INSTRUCTION", "Clinic collection account instruction",
                         f"{source} collection desk\nAccount holder: {PEOPLE[(index + 7) % len(PEOPLE)]}. "
                         "Transfer the patient's treatment proceeds to this private collection account before the infusion is booked.")]
    elif mode == "consistent_fabrication":
        title = f"Continuing care package for {person}"
        story = f"{person} has a specialist appointment at {source}; the family seeks {m(amount)} for the treatment and monitoring package."
        docs = [document("CONSULTANT_NOTE", "Specialty service note",
                         f"{source}\nPatient: {person}\nRecord {ref}, dated {date}. The service recommends a course of monitoring and supportive therapy."),
                document("COST_SCHEDULE", "Treatment cost schedule",
                         f"{source}\nPatient: {person}\nRecord {ref}, dated {date}. Total cost for monitoring and supportive therapy: {m(amount)}. "
                         "The listed amount is due before the next appointment.")]
    elif mode == "medical_provisional":
        title = f"Pending immunotherapy slot for {person}"
        story = f"{person} has been evaluated at {source}; the family is raising {m(amount)} for a treatment window that remains subject to committee approval."
        docs = [document("PROVISIONAL_CLINICAL_PLAN", "Committee review copy",
                         f"{source}\nPatient: {person}\nDraft ref {ref}, dated {date}. "
                         f"Provisional immunotherapy schedule; cost indication {m(amount)}. Final slot assignment is awaiting the clinical board.")]
    elif mode == "medical_shared_cost":
        title = f"Shared oncology costs for {person}"
        story = f"{person}'s care at {source} may receive a family contribution, but the payer and net balance have not yet been confirmed."
        docs = [document("ONCOLOGY_ESTIMATE", "Preliminary treatment estimate",
                         f"{source}\nPatient: {person}\nEstimate {ref}; {date}. Gross estimate {m(amount)}; "
                         "insurance, family contribution and final payable balance are not recorded on this copy.")]
    elif mode == "medical_missing_identity":
        title = f"Sleep study treatment request in {place}"
        story = f"A household is raising {m(amount)} for testing at {source}, but the extract shared with the campaign has no readable patient name."
        docs = [document("LAB_ESTIMATE", "Sleep service fee note",
                         f"{source}\nTesting fee {m(amount)}. Reference {ref}; dated {date}. "
                         "The patient field is obscured in this scan and the medical recommendation is not attached.")]

    elif mode == "education_supported":
        if family == "accessible_exam_studio":
            title = f"Access tools for {person}'s examination term"
            story = f"{person} is registered with {source}. An adjustable reader, audio transcription and invigilator support are listed as examination access costs totalling {m(amount)}."
            invoice = f"Adjustable reader, transcription and examination support total {m(amount)}."
            registration = "Registration remains active for the next examination sitting. The access coordinator approved the accommodation."
        else:
            title = f"Keyboard and transcription set for {person}"
            story = f"{person} is studying endangered language archives at {source}. A compact keyboard, licensed transcription tools and supervised archive hours cost {m(amount)}."
            invoice = f"Compact keyboard, transcription license and supervised archive hours total {m(amount)}."
            registration = "The archive-language student is enrolled this term. The faculty assigned a supervisor for the digitization work."
        docs = [document("ASSESSMENT_ACCESS_INVOICE", "Candidate access invoice",
                         f"{source}\nCandidate: {person}\nAccount {ref}, {date}. {invoice}"),
                document("REGISTRATION_EXTRACT", "Current registration record",
                         f"{source}\nCandidate: {person}\n{registration}")]
    elif mode == "education_research":
        title = f"Coastal audio archive fieldwork for {person}"
        story = f"{person}'s marine acoustics placement at {source} includes boat hire and protected recording equipment. The faculty breakdown totals {m(amount)}."
        docs = [document("FIELDWORK_COSTING", "Marine department fieldwork sheet",
                         f"{source}\nResearch trainee: {person}\nSheet {ref}, {date}. "
                         f"Boat hire, sealed microphones, battery packs and data storage total {m(amount)}."),
                document("PLACEMENT_RECORD", "Faculty field placement record",
                         f"{source}\nTrainee: {person}\nPlacement in marine acoustics is active this term. "
                         "The department has assigned a faculty supervisor for the coastal recording work.")]
    elif mode == "education_duration":
        title = f"Advanced certificate tuition for {person}"
        story = f"{person} says the certificate at {source} runs for eighteen months and is seeking the full program amount of {m(amount)}."
        docs = [document("PROGRAM_CALENDAR", "Course registrar calendar",
                         f"{source}\nApplicant: {person}\nCalendar ref {ref}. The certificate has seven teaching weeks. "
                         "No continuation module is scheduled after this cohort.")]
    elif mode == "education_settled":
        title = f"Term balance for {person}'s design course"
        story = f"{person} asks for {m(amount)} to clear an unpaid term balance at {source}; the office has received nothing."
        docs = [document("STUDENT_LEDGER", "Term account reconciliation",
                         f"{source}\nStudent: {person}\nLedger {ref}, dated {date}. "
                         f"The full balance of {m(amount)} has been paid and the account is settled.")]
    elif mode == "education_quantity":
        title = f"Tablet loan bank for {place} learners"
        story = f"The request lists 54 tablets for the {source} shared-use room; all 54 are included in the supply goal."
        docs = [document("ASSET_RECEIVING_LOG", "Learning lab asset register",
                         f"{source}\nBatch {ref}; {date}. The storeroom recorded 31 tablets in this delivery. "
                         "No follow-on dispatch is shown in the receiving log.")]
    elif mode == "consistent_fabrication":
        title = f"Term allowance and studio access for {person}"
        story = f"{person} is enrolled at {source}; the appeal covers a term allowance and supervised studio access amounting to {m(amount)}."
        docs = [document("ENROLMENT_NOTE", "Student status note",
                         f"{source}\nStudent: {person}\nReference {ref}, {date}. Enrollment is active for the current term."),
                document("STUDENT_ACCOUNT", "Term allowance statement",
                         f"{source}\nStudent: {person}\nReference {ref}, {date}. Total studio access and term allowance: {m(amount)}. "
                         "The balance is due to the institution.")]
    elif mode == "education_conditional":
        title = f"Flight-simulator seat deposit for {person}"
        story = f"{person} has a place at {source} only if the practical test is passed. The appeal asks for a deposit before the score is issued."
        docs = [document("ADMISSIONS_PORTAL_EXPORT", "Applicant reservation screen",
                         f"{source}\nApplicant {person}; ref {ref}; {date}. A simulator seat is held conditionally while the practical score is pending.")]
    elif mode == "education_sponsor_pending":
        title = f"Scholarship payment split for {person}"
        story = f"The student statement from {source} shows a term charge, but the donor's installment has not been posted. The amount requested is {m(amount)}."
        docs = [document("STUDENT_ACCOUNT_IMAGE", "Unverified student account image",
                         f"{source}\nStudent {person}. A sponsor credit is expected but no date or cleared-payment entry appears. "
                         "The copy supplied to the student is cropped at the account reference field.")]
    elif mode == "education_undated":
        title = f"Materials charge at {source}"
        story = f"{person} needs a workshop material charge of {m(amount)} according to an account image without a visible issue date or registrar seal."
        docs = [document("ACCOUNT_SCREENSHOT", "Cropped workshop account screenshot",
                         f"{source}\nStudent: {person}\nMaterials amount {m(amount)}. The date and registrar endorsement are outside the crop.")]

    elif mode == "community_supported":
        if family == "market_food_cooling_room":
            title = f"Shared food cooling room for {place} vendors"
            story = f"Small vendors in {place} need an insulated room to reduce spoilage during feeder outages. The cooperative works order and equipment breakdown total {m(amount)}."
            work = "The committee approved an insulated produce room with backup cooling for the market vendors."
            quote = f"Project: produce room for {place} vendors. Insulation, compressor, wiring and commissioning total {m(amount)}."
        elif family == "earthquake_masonry_repair":
            title = f"Seismic masonry repair on the {place} footpath"
            story = f"After ground movement cracked the hillside footpath, residents asked the council to rebuild two retaining sections. The approved masonry schedule totals {m(amount)}."
            work = "The council approved two retaining-wall sections and a handrail on the public footpath."
            quote = f"Project: stonework, mesh reinforcement and handrail on the public route. Total repair cost: {m(amount)}."
        else:
            title = f"Sorting canopy for the {place} compost route"
            story = f"The producers forum plans a covered sorting bay so market trimmings can be separated before compost collection. A fabricator's bill of materials totals {m(amount)}."
            work = "The forum approved a covered sorting bay for the organic-waste collection route."
            quote = f"Project: canopy, washable floor and bins for the compost route. Fabrication and installation total {m(amount)}."
        docs = [document("WORKS_ORDER", "Cooperative works authorization",
                         f"{source}\nClient: {org}\nOrder {ref}, dated {date}. {work}"),
                document("SUPPLIER_QUOTE", "Supplier's itemized project quotation",
                         f"Supplier to: {org}\nRef {ref}; {date}. {quote}")]
    elif mode == "community_quantity":
        title = f"Modular shade stalls for 72 shoreline sellers"
        story = f"The association requests 72 modular stalls for vendors displaced from the {place} foreshore; every stall is included in the cost goal."
        docs = [document("FABRICATION_DISPATCH", "Supplier completion docket",
                         f"{source}\nDispatch {ref}, {date}. The docket records 36 modular stalls received by the association. "
                         "No additional frame batch is due under this order.")]
    elif mode == "community_settled":
        title = f"Unpaid masonry invoice for {place} flood steps"
        story = f"The association says a contractor is still owed {m(amount)} for the flood steps and asks donors to settle the invoice."
        docs = [document("SUPPLIER_ACCOUNT", "Contractor payment record",
                         f"{source}\nAccount {ref}, {date}. The invoice total of {m(amount)} was paid by bank transfer. "
                         "Supplier balance: nil; contract account closed.")]
    elif mode == "community_permit_pending":
        title = f"Boardwalk repair at the {place} inlet"
        story = f"Residents are considering a public boardwalk repair at the inlet. The proposal is not approved by the shoreline authority."
        docs = [document("SITE_VISIT_NOTE", "Planning desk visit note",
                         f"{source}\nNote {ref}, {date}. The site could support a short public boardwalk, subject to a coastal access permit. "
                         "The permit has not yet been issued.")]
    elif mode == "community_cost_share":
        title = f"Shared roof for the {place} tool library"
        story = f"A partner may contribute half the roofing cost for the association's tool library, but the amount and payment date are not confirmed."
        docs = [document("PARTNER_MEMORANDUM", "Unsigned partner contribution note",
                         f"{source}\nDraft {ref}, {date}. The partner is exploring a contribution toward a common roof. "
                         "No amount or disbursement schedule has been approved.")]
    elif mode == "community_draft":
        title = f"Night lighting near the {place} bus stop"
        story = f"The association requests {m(amount)} for public lighting although the attached meeting extract has not been ratified."
        docs = [document("MEETING_DRAFT", "Unratified committee notes",
                         f"{source}\nWorking notes {ref}; {date}. Members discussed possible lighting near the bus stop. "
                         "The minutes are a draft and no resolution has been adopted.")]
    elif mode == "community_quote_pending":
        title = f"Refrigerated locker for the {place} fish market"
        story = f"A supplier gave a short-lived estimate for a chilled locker. The association has not confirmed the site or its co-funding share."
        docs = [document("BUDGETARY_QUOTE", "Budget estimate without acceptance",
                         f"{source}\nQuote {ref}; {date}. Indicative locker supply is {m(amount)}. "
                         "This budgetary quote expires soon and is not an accepted work order.")]

    if not docs:
        raise AssertionError(f"No synthetic dossier generated for {mode}")
    return {
        "title": title, "category": category, "story": story, "goal_amount": amount,
        "goal_currency": "INR", "beneficiary_name": beneficiary, "beneficiary_type": btype,
        "city": place, "state": "India", "submitted_on": "2026-10-30", "documents": docs,
    }


def generate():
    rows, serial = [], 1
    for category, specs in FAMILIES.items():
        for label, family, source, mode in specs:
            for variant in range(10):
                input_data = build_input(category, label, family, source, mode, variant)
                rows.append({
                    "case_id": f"V3T-{serial:03d}", "ground_truth": label,
                    "scenario_family": family, "document_source": source,
                    "variant": variant + 1, "synthetic": True,
                    "label_basis": ("Authored scenario facts. For consistent-fabrication families the false provenance is known only to the author; the visible dossier contains no reliable detector signal." 
                                   if mode == "consistent_fabrication" else "Authored narrative/document facts; label set before verifier execution."),
                    "expected_action": {"legitimate": "APPROVED", "fraudulent": "FLAG_FOR_REVIEW",
                                        "borderline": "NEEDS_MORE_INFORMATION"}[label],
                    "input": input_data,
                })
                serial += 1
    expected = {"legitimate": 100, "fraudulent": 100, "borderline": 100}
    actual = {label: sum(row["ground_truth"] == label for row in rows) for label in expected}
    if len(rows) != 300 or actual != expected:
        raise AssertionError(f"Unexpected final corpus: {len(rows)} rows, counts={actual}")
    return rows


if __name__ == "__main__":
    rows = generate()
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"wrote {len(rows)} synthetic final cases to {OUT}")
