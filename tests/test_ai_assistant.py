def test_indian_enhance_story_endpoint(client):
    payload = {
        "category": "MEDICAL",
        "goal_amount": 500000.0,
        "rough_notes": "My sister Pooja needs emergency laparoscopic appendectomy and ICU treatment in Delhi. High hospital bills. Need help paying off surgeon fees and room rent.",
        "beneficiary_name": "Pooja",
        "target_audience": "Friends, colleagues and family"
    }

    res = client.post("/api/ai/enhance-story", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "suggested_title" in data
    assert "Pooja" in data["suggested_title"]
    assert "structured_story" in data
    assert "recommended_itemized_breakdown" in data
    assert len(data["recommended_itemized_breakdown"]) >= 3
    assert len(data["transparency_tips"]) > 0

def test_indian_cost_benchmark_endpoint(client):
    payload = {
        "category": "MEDICAL",
        "description": "Cancer chemotherapy treatment sessions",
        "requested_amount": 800000.0
    }
    res = client.post("/api/ai/benchmark-cost", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["benchmark_status"] == "WITHIN_NORMAL_RANGE"
    assert "insight" in data

def test_indian_pre_check_verification_endpoint(client):
    payload = {
        "title": "Clean Water RO Plant for Zilla Parishad School",
        "category": "COMMUNITY",
        "story": "Installing clean RO drinking water plant for 400 school students in rural Solapur, Maharashtra.",
        "goal_amount": 85000.0,
        "city": "Solapur",
        "state": "Maharashtra"
    }
    res = client.post("/api/ai/verify-request", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["authenticity_score"] > 60
    assert "risk_level" in data
    assert "recommendation" in data
