def test_create_and_auto_verify_indian_campaign(client):
    payload = {
        "title": "Supporting Rohit's Pediatric Heart Surgery at Narayana Health",
        "subtitle": "Help save 4-year-old Rohit with urgent open heart congenital defect repair in Bengaluru.",
        "category": "MEDICAL",
        "story": """Rohit was diagnosed with a severe ventricular septal heart defect at Narayana Health, Bengaluru by Dr. Devi Shetty's surgical team.
        The official signed hospital estimate letter totals ₹3,50,000 for open heart surgery and post-operative ICU care.
        We are attaching the hospital estimate letter, ECG reports, and father's Aadhaar card.""",
        "goal_amount": 350000.0,
        "country": "IN",
        "state": "Karnataka",
        "city": "Bengaluru",
        "postal_code": "560099",
        "beneficiary_type": "FAMILY",
        "beneficiary_name": "Rohit Kumar",
        "relationship_to_beneficiary": "Son",
        "hospital_name": "Narayana Health, Bengaluru",
        "hospital_patient_uhid": "NH-BLR-2026-4401",
        "is_80g_tax_exempt": True,
        "direct_hospital_transfer": True,
        "proof_documents": [
            {
                "doc_type": "HOSPITAL_ESTIMATE",
                "title": "Narayana Health Cardiac Estimate Letter",
                "file_url": "https://example.com/nh-estimate.pdf",
                "verified": False
            }
        ]
    }

    response = client.post("/api/campaigns", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["goal_amount"] == 350000.0
    assert data["currency"] == "INR"
    assert data["country"] == "IN"
    assert data["hospital_name"] == "Narayana Health, Bengaluru"
    assert data["authenticity_score"] is not None
    assert data["authenticity_score"] >= 75.0
    assert data["status"] in ("ACTIVE", "PENDING_VERIFICATION")
    campaign_id = data["id"]

    # Test get campaign
    get_res = client.get(f"/api/campaigns/{campaign_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == campaign_id
    assert get_res.json()["currency"] == "INR"

    # Test list campaigns
    list_res = client.get("/api/campaigns")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(c["id"] == campaign_id for c in items)

def test_campaign_verification_endpoint(client):
    create_payload = {
        "title": "Government School Digital Classroom Project in Pune",
        "category": "EDUCATION",
        "story": "Raising ₹1,50,000 to install 5 smart interactive LED display boards in Zilla Parishad Primary School Pune. Principal Kulkarni is overseeing.",
        "goal_amount": 150000.0,
        "city": "Pune",
        "state": "Maharashtra",
        "country": "IN"
    }
    create_res = client.post("/api/campaigns", json=create_payload)
    assert create_res.status_code == 201
    campaign_id = create_res.json()["id"]

    verify_res = client.post(f"/api/campaigns/{campaign_id}/verify")
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert "authenticity_score" in vdata
    assert "risk_level" in vdata
    assert "dimension_scores" in vdata

    audit_res = client.get(f"/api/campaigns/{campaign_id}/audit")
    assert audit_res.status_code == 200
    assert audit_res.json()["campaign_id"] == campaign_id
