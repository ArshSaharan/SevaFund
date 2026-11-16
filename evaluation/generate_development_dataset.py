"""Create the fixed, synthetic v1 development corpus with family/source groups."""
import json
from pathlib import Path

OUT = Path(__file__).with_name("development_scenarios_v1.jsonl")
FAMILIES = [
    ("MEDICAL", "dialysis_power", "district_clinic_billing_desk", "home dialysis power backup", "A clinic care plan lists a battery unit and safe wiring for a patient receiving home dialysis."),
    ("MEDICAL", "rare_dietary_formula", "pediatric_nutritionist_letter", "specialized nutrition supply", "A pediatric plan specifies a month-by-month supply of prescribed elemental formula."),
    ("MEDICAL", "mobility_repair", "prosthetics_workshop_quote", "mobility device repair", "A rehabilitation team recommends a custom brace repair and gait fitting before discharge."),
    ("MEDICAL", "rural_transport", "ambulance_cooperative_log", "treatment travel costs", "A patient in a remote block needs scheduled transport for recurring oncology visits."),
    ("EDUCATION", "laboratory_access", "campus_procurement_office", "science lab access", "A public college seeks accessible lab tools for a named cohort of first-year students."),
    ("EDUCATION", "apprenticeship_tools", "trade_guild_tool_ledger", "apprenticeship equipment", "An apprentice needs a calibrated toolkit required for supervised workshop hours."),
    ("EDUCATION", "rural_hostel", "hostel_warden_fee_register", "student accommodation", "A student from a distant district requests a term of hostel charges near the teaching hospital."),
    ("EDUCATION", "exam_access", "testing_center_accommodation_notice", "exam accessibility", "A learner requires a screen reader license and transport for an entrance examination."),
    ("COMMUNITY", "water_testing", "municipal_water_lab_report", "shared well restoration", "Residents seek testing and a pump seal for a shared well serving several lanes."),
    ("COMMUNITY", "storm_shelter", "ward_engineer_site_memo", "community shelter repairs", "A neighborhood group requests roof fasteners and dry sleeping mats after storm damage."),
    ("COMMUNITY", "food_cold_chain", "cooperative_dairy_temperature_log", "food distribution storage", "A volunteer network needs insulated boxes to keep donated groceries safe during distribution."),
    ("COMMUNITY", "accessible_route", "village_council_measurement_book", "accessible route works", "A village committee plans a short ramp and handrail linking a clinic to the bus stop."),
]
NAMES = ["Mira Sen", "Kabir Das", "Leela Nair", "Ishan Roy", "Tara Iqbal", "Devika Paul", "Rohan Gill", "Anika Bose", "Farid Ali", "Meera Joseph"]


def make_rows():
    rows = []
    family_number = 0
    for category, family, source, subject, base_story in FAMILIES:
        fold = f"fold-{family_number // 4 + 1}"
        for index in range(10):
            label = "legitimate" if index < 4 else "fraudulent" if index < 8 else "borderline"
            case_num = len(rows) + 1
            person = NAMES[(family_number * 3 + index) % len(NAMES)]
            amount = 28500 + family_number * 7300 + index * 1150
            claim_id = f"REQ-{family_number + 1:02d}-{index + 1:02d}"
            story = f"{base_story} The beneficiary is {person}; file {claim_id} requests ₹{amount:,} for this defined purpose."
            relation = "supports" if label == "legitimate" else "contradicts" if label == "fraudulent" else "incomplete"
            doc_title = f"Synthetic {source.replace('_', ' ')} record {claim_id}"
            if relation == "supports":
                evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Beneficiary {person}. Approved purpose: {subject}. Amount ₹{amount:,}. Status: current and payable."
            elif relation == "contradicts":
                # Conflicts are varied across amount, identity, duration, quantity,
                # reimbursement, and purpose so no one phrase dominates.
                conflict = index % 6
                if conflict == 0:
                    evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Beneficiary {person}. Approved purpose: {subject}. Amount ₹{amount + 43000:,}; this is the final amount due."
                elif conflict == 1:
                    evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Payee of record is a different applicant, Nilesh Varma. Amount ₹{amount:,}."
                elif conflict == 2:
                    evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Approved duration is six weeks; no later period is authorized. Amount ₹{amount:,}."
                elif conflict == 3:
                    evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Delivery register shows 18 units supplied and signed for; a second purchase is not listed. Amount ₹{amount:,}."
                elif conflict == 4:
                    evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Amount ₹{amount:,}. Invoice status: settled in full; no outstanding balance."
                else:
                    evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Authorization covers a different activity, not {subject}. Amount ₹{amount:,}."
                story += " The requested record states an outstanding balance for the requested period."
            else:
                evidence = f"[Synthetic {source.replace('_', ' ')} record] File {claim_id}. Preliminary review only; final amount, beneficiary match, and approval status are not yet recorded."
                story += " A staff member has not yet confirmed whether the preliminary amount is the final payable figure."
            documents = [] if label == "borderline" and index == 9 else [
                {"doc_type": source.upper(), "title": doc_title, "content": evidence}
            ]
            rows.append({
                "case_id": f"DEV-{case_num:03d}", "ground_truth": label,
                "scenario_family": family, "document_source": source,
                "group_fold": fold, "evidence_relation": "unavailable" if not documents else relation,
                "synthetic": True,
                "input": {"title": f"Support for {subject}: {person}", "category": category,
                          "story": story, "goal_amount": amount, "beneficiary_name": person,
                          "beneficiary_type": "SELF", "city": "Mysuru", "state": "Karnataka",
                          "documents": documents},
            })
        family_number += 1
    return rows


if __name__ == "__main__":
    rows = make_rows()
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"Wrote {len(rows)} synthetic scenarios to {OUT}")
