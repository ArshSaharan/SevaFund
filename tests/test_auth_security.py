import pytest
from app.models.user import User

def test_google_auth_flow(client, db_session):
    # 1. Authenticate with Google ID token (using simulated dev token)
    res = client.post("/api/auth/google", json={"id_token": "mock_google_ananya_sharma"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    user_info = data["user"]
    assert user_info["email"] == "ananya@gmail.com"
    assert user_info["is_email_verified"] is True
    assert user_info["is_identity_verified"] is True

    # 2. Re-authenticating with the same Google ID logs into the existing user
    res2 = client.post("/api/auth/google", json={"id_token": "mock_google_ananya_sharma"})
    assert res2.status_code == 200
    assert res2.json()["user"]["id"] == user_info["id"]

    # 3. Use access token to fetch profile
    token = data["access_token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "ananya@gmail.com"

def test_indian_mobile_otp_flow(client, db_session):
    phone = "9876543210"

    # 1. Invalid phone format check
    invalid_res = client.post("/api/auth/otp/send", json={"phone_number": "12345"})
    assert invalid_res.status_code == 400
    assert "Invalid Indian mobile number" in invalid_res.json()["detail"]

    # 2. Send valid OTP
    send_res = client.post("/api/auth/otp/send", json={"phone_number": phone})
    assert send_res.status_code == 200
    send_data = send_res.json()
    assert send_data["phone_number"] == "+919876543210"
    otp_code = send_data["dev_otp"]
    assert len(otp_code) == 6

    # 3. Failed OTP attempt check
    bad_verify = client.post("/api/auth/otp/verify", json={
        "phone_number": phone,
        "otp": "000000"
    })
    assert bad_verify.status_code == 400
    assert "Invalid OTP code" in bad_verify.json()["detail"]

    # 4. Successful OTP verification
    good_verify = client.post("/api/auth/otp/verify", json={
        "phone_number": phone,
        "otp": otp_code,
        "full_name": "Rohan Deshmukh"
    })
    assert good_verify.status_code == 200
    verify_data = good_verify.json()
    assert "access_token" in verify_data
    assert verify_data["user"]["phone_number"] == "+919876543210"
    assert verify_data["user"]["is_phone_verified"] is True
    assert verify_data["user"]["full_name"] == "Rohan Deshmukh"

    # 5. Access protected /auth/me with OTP-issued JWT
    auth_token = verify_data["access_token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["phone_number"] == "+919876543210"

def test_otp_rate_limiting(client, db_session):
    rate_test_phone = "9811122233"
    # Send 3 OTPs (within allowed limit)
    for _ in range(3):
        res = client.post("/api/auth/otp/send", json={"phone_number": rate_test_phone})
        assert res.status_code == 200

    # 4th OTP request within 10 minutes must trigger HTTP 429 Too Many Requests
    blocked_res = client.post("/api/auth/otp/send", json={"phone_number": rate_test_phone})
    assert blocked_res.status_code == 429
    assert "Too many OTP requests" in blocked_res.json()["detail"]

def test_admin_promotion_and_security_headers(client, db_session):
    # 1. Register a regular user
    reg_res = client.post("/api/auth/register", json={
        "email": "candidate@example.com",
        "password": "strongPassword123",
        "full_name": "Admin Candidate"
    })
    assert reg_res.status_code == 201
    user_id = reg_res.json()["user"]["id"]
    user_token = reg_res.json()["access_token"]

    # 2. Candidate cannot access admin flagged queue
    forbidden_res = client.get("/api/admin/flagged", headers={"Authorization": f"Bearer {user_token}"})
    assert forbidden_res.status_code == 403

    # 3. Promote user to admin with platform secret key
    from app.config import settings
    promote_res = client.post("/api/auth/promote-admin", json={
        "user_id": user_id,
        "secret_key": settings.SECRET_KEY
    })
    assert promote_res.status_code == 200
    assert promote_res.json()["role"] == "ADMIN"

    # 4. Login to obtain fresh admin JWT
    login_res = client.post("/api/auth/login", json={
        "email": "candidate@example.com",
        "password": "strongPassword123"
    })
    admin_token = login_res.json()["access_token"]

    # 5. Now user has ADMIN rights
    admin_queue_res = client.get("/api/admin/flagged", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_queue_res.status_code == 200

    # 6. Verify security headers are present on response
    assert admin_queue_res.headers.get("X-Content-Type-Options") == "nosniff"
    assert admin_queue_res.headers.get("X-Frame-Options") == "DENY"
    assert admin_queue_res.headers.get("X-XSS-Protection") == "1; mode=block"
