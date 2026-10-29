from app.models.user import User
from app.services.security import hash_password, create_access_token

def test_admin_flagged_queue_and_decision(client, db_session):
    # 0. Create normal user and admin user in test DB
    normal_user = User(
        email="regular@example.com",
        hashed_password=hash_password("password123"),
        full_name="Regular Donor",
        role="USER",
        is_identity_verified=True
    )
    admin_user = User(
        email="admin@sevafund.in",
        hashed_password=hash_password("adminpass"),
        full_name="Super Admin",
        role="ADMIN",
        is_identity_verified=True
    )
    db_session.add_all([normal_user, admin_user])
    db_session.commit()
    db_session.refresh(normal_user)
    db_session.refresh(admin_user)

    user_token = create_access_token({"sub": str(normal_user.id), "role": normal_user.role})
    admin_token = create_access_token({"sub": str(admin_user.id), "role": admin_user.role})

    user_headers = {"Authorization": f"Bearer {user_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a campaign that gets flagged
    payload = {
        "title": "Need funds for undisclosed personal reasons",
        "category": "OTHER",
        "story": "Please give money urgently. Do not ask questions. Wire immediately.",
        "goal_amount": 90000.0
    }
    create_res = client.post("/api/campaigns", json=payload, headers=user_headers)
    assert create_res.status_code == 201
    campaign_id = create_res.json()["id"]

    # 2. RBAC Verification: Unauthenticated request to admin endpoint fails with 401
    unauth_res = client.get("/api/admin/flagged")
    assert unauth_res.status_code == 401

    # 3. RBAC Verification: Regular user request to admin endpoint fails with 403 Forbidden
    forbidden_res = client.get("/api/admin/flagged", headers=user_headers)
    assert forbidden_res.status_code == 403
    assert "Admin privileges required" in forbidden_res.json()["detail"]

    # 4. Check flagged queue as authenticated ADMIN
    flagged_res = client.get("/api/admin/flagged", headers=admin_headers)
    assert flagged_res.status_code == 200
    flagged_list = flagged_res.json()
    assert any(c["id"] == campaign_id for c in flagged_list)

    # 5. Non-admin cannot submit decision (403 Forbidden)
    decision_payload = {
        "decision": "REJECT",
        "notes": "Rejected due to complete absence of verifiable evidence and high risk indicators."
    }
    user_dec_res = client.post(f"/api/admin/campaigns/{campaign_id}/decision", json=decision_payload, headers=user_headers)
    assert user_dec_res.status_code == 403

    # 6. Admin accepts or rejects demand (200 OK)
    admin_dec_res = client.post(f"/api/admin/campaigns/{campaign_id}/decision", json=decision_payload, headers=admin_headers)
    assert admin_dec_res.status_code == 200
    assert admin_dec_res.json()["status"] == "REJECTED"

    # 7. View audits list as admin
    verifs_res = client.get("/api/admin/verifications", headers=admin_headers)
    assert verifs_res.status_code == 200
    assert len(verifs_res.json()) > 0

    # 8. Check immutable audit logs
    audit_logs_res = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert audit_logs_res.status_code == 200
    assert len(audit_logs_res.json()) > 0
    assert audit_logs_res.json()[0]["action"] == "CAMPAIGN_REJECTED"
