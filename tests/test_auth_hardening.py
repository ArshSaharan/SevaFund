"""Authentication hardening regression tests: Google ID tokens, OTP disclosure, and the signing key.

Google tokens are signed with an isolated test key (conftest.google_signer) and verified by google-auth's real code;
no network is used.  No test prints a key.
"""
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import jwt as pyjwt
import pytest

from app.models.user import User
from app.services import security

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT_KEY = re.search(r'getenv\("SECRET_KEY",\s*"([^"]+)"\)', (ROOT / "app/config.py").read_text()).group(1)


def google_login(client, token):
    return client.post("/api/auth/google", json={"id_token": token})


def no_user(db, email):
    return db.query(User).filter(User.email == email).first() is None


# ------------------------------------------------------------------ Google sign-in
@pytest.mark.parametrize("token", ["mock_google_eve", "mock_google_admin_attacker", "mock_google_"])
def test_mock_google_tokens_are_rejected(client, db_session, google_signer, token):
    res = google_login(client, token)
    assert res.status_code == 401 and "access_token" not in res.json()
    assert no_user(db_session, "eve@gmail.com") and no_user(db_session, "admin@gmail.com")


def test_mock_google_tokens_are_rejected_when_google_is_not_configured(client, db_session, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    res = google_login(client, "mock_google_eve")
    assert res.status_code == 503 and "access_token" not in res.json()
    assert no_user(db_session, "eve@gmail.com")


@pytest.mark.parametrize("case", ["forged_signature", "unsigned_alg_none", "hs256_with_app_secret", "garbage"])
def test_forged_google_tokens_are_rejected(client, db_session, google_signer, case):
    email = f"forged-{case}@gmail.com"
    token = {"forged_signature": lambda: google_signer.token(email=email, forged=True),
             "unsigned_alg_none": lambda: google_signer.token(email=email, algorithm="none"),
             "hs256_with_app_secret": lambda: pyjwt.encode({"iss": "https://accounts.google.com", "aud": google_signer.CLIENT_ID,
                                                            "sub": "x", "email": email, "email_verified": True,
                                                            "iat": 1, "exp": 4102444800}, security.JWT_SECRET,
                                                           algorithm="HS256", headers={"kid": google_signer.kid}),
             "garbage": lambda: "not.a.token"}[case]()
    res = google_login(client, token)
    assert res.status_code == 401 and no_user(db_session, email)


def test_expired_google_token_is_rejected(client, db_session, google_signer):
    res = google_login(client, google_signer.token(email="expired@gmail.com", expires_in=-120))
    assert res.status_code == 401 and no_user(db_session, "expired@gmail.com")


@pytest.mark.parametrize("claims", [{"aud": "another-app.apps.googleusercontent.com"}, {"iss": "https://evil.example.com"},
                                    {"iss": "accounts.google.com.evil.example"}])
def test_wrong_audience_or_issuer_is_rejected(client, db_session, google_signer, claims):
    res = google_login(client, google_signer.token(email="claims@gmail.com", **claims))
    assert res.status_code == 401 and no_user(db_session, "claims@gmail.com")


def test_unverified_google_email_is_rejected(client, db_session, google_signer):
    res = google_login(client, google_signer.token(email="unverified@gmail.com", email_verified=False))
    assert res.status_code == 401 and no_user(db_session, "unverified@gmail.com")


@pytest.mark.parametrize("client_id", ["", "your-google-client-id.apps.googleusercontent.com", "not-a-client-id"])
def test_google_sign_in_fails_closed_without_a_real_client_id(client, google_signer, monkeypatch, client_id):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", client_id)
    assert google_login(client, google_signer.token(email="closed@gmail.com")).status_code == 503


def test_valid_google_token_still_signs_in(client, db_session, google_signer):
    res = google_login(client, google_signer.token(email="valid.google@gmail.com", sub="google-sub-valid"))
    assert res.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "valid.google@gmail.com"


# ------------------------------------------------------------------ nobody obtains a token without credentials
@pytest.fixture
def sms(monkeypatch):
    sent, mode = {}, {"provider": "TEST_SMS", "success": True}

    async def fake_send(phone_number, otp_code):
        sent[phone_number] = otp_code
        return dict(mode)
    import app.services.sms_service as sms_service
    monkeypatch.setattr(sms_service, "send_real_sms_otp", fake_send)
    return sent, mode


def test_otp_is_never_returned_and_fails_closed_without_sms(client, db_session, sms):
    sent, mode = sms
    ok = client.post("/api/auth/otp/send", json={"phone_number": "9822001100"})
    assert ok.status_code == 200 and ok.json()["dev_otp"] is None and sent["+919822001100"] not in ok.text
    for provider, success in (("SIMULATION", True), ("FAST2SMS", False)):
        mode.update(provider=provider, success=success)
        phone = "9822001101" if provider == "SIMULATION" else "9822001102"
        res = client.post("/api/auth/otp/send", json={"phone_number": phone})
        assert res.status_code == 503 and sent[f"+91{phone}"] not in res.text
        verify = client.post("/api/auth/otp/verify", json={"phone_number": phone, "otp": sent[f"+91{phone}"]})
        assert verify.status_code == 400 and "access_token" not in verify.json()     # the undelivered code is dead


def test_unauthenticated_requests_obtain_no_token(client, db_session):
    client.post("/api/auth/register", json={"email": "holder@example.com", "password": "Correct-Horse-1",
                                            "full_name": "Holder"})
    for body in ({"email": "holder@example.com", "password": "wrong"}, {"email": "nobody@example.com", "password": "x"}):
        res = client.post("/api/auth/login", json=body)
        assert res.status_code == 401 and "access_token" not in res.json()
    assert client.get("/api/auth/me").status_code == 401
    other_key = pyjwt.encode({"sub": "1", "role": "ADMIN", "iat": 1, "exp": 4102444800}, secrets.token_urlsafe(48),
                             algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {other_key}"}).status_code == 401
    for key in ("guess", CONFIG_DEFAULT_KEY):                     # no shared secret grants admin rights
        assert client.post("/api/auth/promote-admin", json={"user_id": 1, "secret_key": key}).status_code == 401


def test_password_login_still_works(client, db_session):
    reg = client.post("/api/auth/register", json={"email": "still.works@example.com", "password": "Correct-Horse-2",
                                                  "full_name": "Still Works"})
    assert reg.status_code == 201
    login = client.post("/api/auth/login", json={"email": "still.works@example.com", "password": "Correct-Horse-2"})
    assert login.status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).status_code == 200


# ------------------------------------------------------------------ signing key fails closed
@pytest.mark.parametrize("key", ["", "   ", "short-key", "a" * 64, "REPLACE_ME_with_a_random_secret_DO_NOT_USE_THIS_PLACEHOLDER",
                                 "your-secret-key-goes-here-and-is-long-enough-123", CONFIG_DEFAULT_KEY])
def test_insecure_signing_keys_are_refused(key):
    with pytest.raises(security.InsecureSigningKeyError) as error:
        security.require_signing_key(key)
    assert (key.strip() == "" or key not in str(error.value))


def test_a_random_signing_key_is_accepted():
    key = secrets.token_urlsafe(48)
    assert security.require_signing_key(key) == key


@pytest.mark.parametrize("key_kind", ["empty", "public_default", "placeholder", "strong"])
def test_application_refuses_to_start_with_an_insecure_key(tmp_path, key_kind):
    key = {"empty": "", "public_default": CONFIG_DEFAULT_KEY, "placeholder": "REPLACE_ME_with_a_random_secret_DO_NOT_USE",
           "strong": secrets.token_urlsafe(48)}[key_kind]
    env = {**os.environ, "SECRET_KEY": key, "GEMINI_API_KEY": "", "DATABASE_URL": f"sqlite:///{tmp_path / 'startup.db'}"}
    proc = subprocess.run([sys.executable, "-c", "import app.main"], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=120)
    if key_kind == "strong":
        assert proc.returncode == 0, proc.stderr[-500:]
    else:
        assert proc.returncode != 0 and "Refusing to start" in proc.stderr
        assert not key or key not in proc.stderr + proc.stdout
