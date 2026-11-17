import asyncio
from app.services.ai_verifier import ai_verifier
from app.services.fraud_detector import analyze_cost_benchmark, detect_red_flags, extract_specificity_signals

def test_genuine_indian_medical_campaign_high_authenticity():
    story = """
    Our 7-year-old son Aarav is undergoing acute leukemia chemotherapy at Tata Memorial Hospital in Mumbai 
    under Dr. Advani (Patient UHID: TMH-MUM-8812).
    The official signed hospital estimate letter totals ₹8,50,000 for multi-agent chemotherapy, 
    platelet transfusions, and pediatric ward charges.
    We are attaching the doctor's prescription, hospital estimate letter, and parent Aadhaar card.
    """
    proof_docs = [
        {"doc_type": "HOSPITAL_ESTIMATE", "title": "Tata Memorial Estimate Letter", "file_url": "https://example.com/tmh-estimate.pdf"}
    ]

    result = asyncio.run(ai_verifier.verify_campaign_request(
        title="Aarav's Cancer Treatment at Tata Memorial Hospital",
        category="MEDICAL",
        story=story,
        goal_amount=850000.0,
        beneficiary_name="Aarav Sharma",
        beneficiary_type="FAMILY",
        location="Mumbai, Maharashtra",
        proof_documents=proof_docs
    ))

    assert result.authenticity_score >= 80.0
    assert result.risk_level == "LOW"
    assert result.recommendation == "AUTO_APPROVE"
    assert len(result.positive_signals) > 0
    assert len(result.red_flags) == 0

def test_indian_scam_pattern_critical_risk():
    scam_story = """
    Send to my personal UPI right now or PhonePe!
    Secret babaji ayurvedic miracle cure for cancer 100% guarantee in 3 days!
    Send ₹50,00,000 immediately without asking any questions or doctor bills.
    """

    result = asyncio.run(ai_verifier.verify_campaign_request(
        title="SECRET BABAJI MIRACLE CURE",
        category="MEDICAL",
        story=scam_story,
        goal_amount=5000000.0,
        beneficiary_name=None,
        beneficiary_type="SELF",
        location=None,
        proof_documents=[]
    ))

    assert result.authenticity_score < 40.0
    assert result.risk_level in ("HIGH", "CRITICAL")
    assert result.recommendation in ("REJECT", "NEEDS_MORE_INFO")
    assert any("upi" in rf.lower() or "miracle" in rf.lower() for rf in result.red_flags)

def test_indian_cost_benchmark_detection():
    # Laparoscopic appendectomy in India (normal range ₹25k - ₹1.4L)
    res = analyze_cost_benchmark("MEDICAL", "Laparoscopic appendectomy surgery at hospital", 60000.0)
    assert res is not None
    assert res["benchmark_status"] == "WITHIN_NORMAL_RANGE"

    # Suspiciously excessive appendectomy in India (₹25,00,000 for a ₹60,000 procedure)
    res_high = analyze_cost_benchmark("MEDICAL", "Laparoscopic appendectomy surgery at hospital", 2500000.0)
    assert res_high is not None
    assert res_high["benchmark_status"] == "SUSPICIOUSLY_EXCESSIVE"

def test_indian_red_flag_scanner():
    flags, penalty = detect_red_flags("Send to my personal UPI number directly via GPay!")
    assert len(flags) > 0
    assert penalty > 0

def test_indian_specificity_extractor():
    signals, score = extract_specificity_signals(
        "Admitted to AIIMS New Delhi under Dr. Gupta for leukemia chemotherapy. Estimate letter attached.",
        location="New Delhi"
    )
    assert score >= 50.0
    assert any("hospital" in s.lower() or "aiims" in s.lower() for s in signals)

def test_education_specificity_uses_education_evidence():
    signals, score = extract_specificity_signals(
        "Sahyadri Public School fee notice for student ID EDU-2041 lists tuition, books, and the July payment period.",
        location="Jaipur, Rajasthan",
        category="EDUCATION",
    )
    assert score >= 65.0
    assert any("education" in signal.lower() or "institution" in signal.lower() for signal in signals)

def test_explicit_guaranteed_cure_is_flagged_across_wording_variants():
    flags, _ = detect_red_flags("The treatment promises a guaranteed recovery in days through a secret cure without a clinician.")
    assert any("unverified" in flag.lower() or "cure" in flag.lower() for flag in flags)

def test_advance_release_fee_is_flagged_without_medical_context():
    flags, _ = detect_red_flags("Pay an upfront release charge to receive the promised education grant.")
    assert any("fee" in flag.lower() or "advance" in flag.lower() for flag in flags)

def test_brief_story_is_missing_information_not_a_fraud_flag():
    flags, _ = detect_red_flags("Help needed for my family.")
    assert flags == []

def test_education_verification_requests_category_relevant_proof():
    result = ai_verifier._verify_with_local_heuristics(
        title="Help with education costs",
        category="EDUCATION",
        story="A student needs help with course expenses.",
        goal_amount=90000,
        beneficiary_name="Riya Patel",
        beneficiary_type="SELF",
        location="Jaipur, Rajasthan",
        proof_documents=[],
    )
    requirements = " ".join(result.missing_requirements).lower()
    assert "fee notice" in requirements or "enrollment" in requirements
    assert "hospital estimate" not in requirements
