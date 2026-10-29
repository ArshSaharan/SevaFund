def test_indian_donation_via_upi_and_80g_receipt(client):
    # 1. Create Indian campaign
    c_res = client.post("/api/campaigns", json={
        "title": "Delhi Flood Relief Clean Drinking Water",
        "category": "EMERGENCY",
        "story": "Providing clean water tankers to Yamuna flood relief camps across North Delhi.",
        "goal_amount": 200000.0,
        "city": "New Delhi",
        "state": "Delhi",
        "country": "IN"
    })
    assert c_res.status_code == 201
    campaign_id = c_res.json()["id"]

    # 2. Make UPI donation of ₹2,000 with ₹100 tip and PAN card for 80G tax exemption
    donation_payload = {
        "amount": 2000.0,
        "tip_amount": 100.0,
        "donor_name": "Rohan Malhotra",
        "donor_email": "rohan@example.com",
        "donor_phone": "9876543210",
        "donor_pan": "ABCDE1234F",
        "payment_method": "UPI",
        "upi_id": "rohan@okhdfcbank",
        "support_message": "Stay safe, Delhi!",
        "is_anonymous": False
    }

    donate_res = client.post(f"/api/campaigns/{campaign_id}/donate", json=donation_payload)
    assert donate_res.status_code == 201
    receipt = donate_res.json()
    assert receipt["campaign_id"] == campaign_id
    assert receipt["amount"] == 2000.0
    assert receipt["tip_amount"] == 100.0
    assert receipt["total_charged"] == 2100.0
    assert receipt["currency"] == "INR"
    assert receipt["payment_method"] == "UPI"
    assert receipt["tax_exemption_80g_number"] is not None
    assert receipt["tax_exemption_80g_number"].startswith("80G-")
    assert receipt["transaction_ref"].startswith("TXN-IN-")

    # 3. Check campaign updated funds
    camp_res = client.get(f"/api/campaigns/{campaign_id}")
    cdata = camp_res.json()
    assert cdata["current_amount"] == 2000.0
    assert cdata["donor_count"] == 1
    assert cdata["currency"] == "INR"

    # 4. Make an anonymous UPI donation of ₹500
    anon_res = client.post(f"/api/campaigns/{campaign_id}/donate", json={
        "amount": 500.0,
        "tip_amount": 0.0,
        "donor_name": "Secret Donor",
        "payment_method": "UPI",
        "is_anonymous": True
    })
    assert anon_res.status_code == 201

    # Check privacy masking
    donations_res = client.get(f"/api/campaigns/{campaign_id}/donations")
    assert donations_res.status_code == 200
    donations = donations_res.json()
    assert len(donations) == 2
    anon_item = next(d for d in donations if d["is_anonymous"])
    assert anon_item["donor_name"] == "Anonymous Supporter"
    assert anon_item["currency"] == "INR"

    # 5. Receipt lookup
    ref = receipt["transaction_ref"]
    rec_res = client.get(f"/api/donations/{ref}")
    assert rec_res.status_code == 200
    assert rec_res.json()["transaction_ref"] == ref
    assert rec_res.json()["currency"] == "INR"

def test_razorpay_gateway_order_and_admin_donation_ledger(client, db_session):
    from app.models.user import User
    from app.services.security import hash_password, create_access_token

    # 1. Create normal user and admin user in test DB
    normal_user = User(
        email="donor.citizen@example.com",
        hashed_password=hash_password("password123"),
        full_name="Citizen Donor",
        role="USER",
        is_identity_verified=True
    )
    admin_user = User(
        email="auditor.admin@crowdfund-trust.in",
        hashed_password=hash_password("adminpass123"),
        full_name="Chief Auditor",
        role="ADMIN",
        is_identity_verified=True
    )
    db_session.add_all([normal_user, admin_user])
    db_session.commit()
    db_session.refresh(normal_user)
    db_session.refresh(admin_user)

    user_token = create_access_token({"sub": str(normal_user.id), "role": normal_user.role})
    admin_token = create_access_token({"sub": str(admin_user.id), "role": admin_user.role})

    # 2. Create campaign with a specific requested beneficiary
    c_res = client.post("/api/campaigns", json={
        "title": "Heart Surgery for Master Kabir (Age 5)",
        "category": "MEDICAL",
        "story": "Supporting pediatric open-heart surgery at Narayana Hrudayalaya Bangalore.",
        "goal_amount": 500000.0,
        "beneficiary_name": "Master Kabir Sharma",
        "beneficiary_type": "FAMILY",
        "hospital_name": "Narayana Hrudayalaya",
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN"
    })
    assert c_res.status_code == 201
    campaign_id = c_res.json()["id"]

    # 3. Create payment gateway order
    order_res = client.post("/api/donations/create-order", json={
        "campaign_id": campaign_id,
        "amount": 5000.0,
        "currency": "INR"
    })
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["campaign_id"] == campaign_id
    assert order_data["amount"] == 500000  # 5000 INR = 500000 paise
    assert order_data["currency"] == "INR"
    assert order_data["order_id"].startswith("order_")

    # 4. Complete donation with gateway payment ref
    donate_res = client.post(f"/api/campaigns/{campaign_id}/donate", json={
        "amount": 5000.0,
        "tip_amount": 150.0,
        "donor_name": "Anita Desai",
        "donor_email": "anita.desai@example.com",
        "donor_phone": "9876500001",
        "donor_pan": "ABCDE9999Z",
        "payment_method": "RAZORPAY",
        "gateway_order_id": order_data["order_id"],
        "gateway_payment_id": "pay_mock_998877",
        "gateway_signature": "sig_mock_signature",
        "is_anonymous": True,  # Anonymous to public
        "support_message": "Get well soon, little champion!"
    })
    assert donate_res.status_code == 201
    receipt = donate_res.json()
    assert receipt["gateway_order_id"] == order_data["order_id"]
    assert receipt["gateway_payment_id"] == "pay_mock_998877"

    # 5. Test Admin Donations Ledger RBAC:
    # 5a. Anonymous user blocked (401)
    unauth_res = client.get("/api/admin/donations")
    assert unauth_res.status_code == 401

    # 5b. Regular non-admin user blocked (403)
    user_headers = {"Authorization": f"Bearer {user_token}"}
    forbidden_res = client.get("/api/admin/donations", headers=user_headers)
    assert forbidden_res.status_code == 403

    # 5c. Admin user access granted (200)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_res = client.get("/api/admin/donations", headers=admin_headers)
    assert admin_res.status_code == 200
    data = admin_res.json()
    assert "items" in data
    assert "summary" in data
    assert data["summary"]["total_donations_count"] >= 1
    assert data["summary"]["total_amount_raised"] >= 5000.0

    # Verify that the admin can check:
    # - How much was paid (amount = 5000.0)
    # - Who paid (donor_name = 'Anita Desai', real email, phone, PAN, even though is_anonymous is True)
    # - To whom: the requested person (beneficiary_name = 'Master Kabir Sharma')
    found_item = next(item for item in data["items"] if item["gateway_order_id"] == order_data["order_id"])
    assert found_item["amount"] == 5000.0
    assert found_item["donor_name"] == "Anita Desai"
    assert found_item["is_anonymous"] is True
    assert found_item["donor_email"] == "anita.desai@example.com"
    assert found_item["donor_phone"] == "9876500001"
    assert found_item["donor_pan"] == "ABCDE9999Z"
    assert found_item["beneficiary_name"] == "Master Kabir Sharma"
    assert found_item["hospital_name"] == "Narayana Hrudayalaya"
    assert found_item["campaign_title"] == "Heart Surgery for Master Kabir (Age 5)"
