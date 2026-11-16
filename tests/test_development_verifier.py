import json
from pathlib import Path

import pytest

from app.services.development_verifier import verify_development_case


@pytest.mark.parametrize("claim,evidence,kind", [
    ("The invoice is for ₹75,000", "Invoice total ₹175,000", "amount"),
    ("Funds will go to Anaya Rao", "Account holder: Dev Rao", "identity"),
    ("Therapy lasts twelve months", "Approved plan duration: ten weeks", "duration"),
    ("The request covers 40 kits", "Packing list contains 24 kits", "quantity"),
    ("The bill remains unpaid", "Receipt marked paid in full", "reimbursement"),
    ("The request is for a water pump", "Authorization covers a different activity, not a water pump", "purpose"),
])
def test_explicit_claim_document_conflict_routes_to_review(claim, evidence, kind):
    output = verify_development_case(
        title="Community support", category="COMMUNITY", story=claim,
        goal_amount=100000, beneficiary_name="Anaya Rao", documents=[evidence],
    )
    assert output.evidence_relation == "contradicts"
    assert kind in " ".join(output.evidence_conflicts).lower()
    assert output.result.recommendation == "FLAG_FOR_REVIEW"


def test_missing_or_unreadable_documents_request_more_information():
    missing = verify_development_case("Tuition request", "EDUCATION", "Fees due next term", 45000, documents=[])
    unreadable = verify_development_case("Tuition request", "EDUCATION", "Fees due next term", 45000, documents=["[UNREADABLE]"])
    assert missing.result.recommendation == "NEEDS_MORE_INFO"
    assert unreadable.result.recommendation == "NEEDS_MORE_INFO"


def test_unusual_medical_cost_alone_does_not_imply_fraud():
    output = verify_development_case(
        "Home dialysis power backup", "MEDICAL",
        "A patient needs a battery system to keep prescribed dialysis equipment running during outages.",
        920000, documents=["Hospital note confirms home dialysis and power interruptions."],
    )
    assert output.result.recommendation != "REJECT"
    assert output.evidence_relation in {"supports", "incomplete"}


def test_category_unrelated_document_requests_category_specific_proof():
    output = verify_development_case(
        "Student lab equipment", "EDUCATION", "A college student needs an accessible microscope for the biology course.",
        56000, documents=["Synthetic animal clinic record. Veterinary appointment for a dog next week."],
    )
    assert output.evidence_relation == "incomplete"
    assert output.result.recommendation == "NEEDS_MORE_INFO"


@pytest.mark.parametrize("case_id", ["IND-064", "IND-070"])
def test_known_autoapproved_contradiction_regressions(case_id):
    path = Path(__file__).resolve().parents[1] / "evaluation" / "independent_benchmark_100.jsonl"
    case = next(json.loads(line) for line in path.read_text().splitlines() if json.loads(line)["case_id"] == case_id)
    payload = case["input"]
    output = verify_development_case(
        payload["title"], payload["category"], payload["story"], payload["goal_amount"],
        beneficiary_name=payload.get("beneficiary_name"),
        documents=[doc["content"] for doc in payload.get("documents", [])],
    )
    assert output.result.recommendation not in {"AUTO_APPROVE", "REJECT"}
