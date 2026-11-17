"""Running SevaFund without SMS credits: email and password is the primary sign-in, phone verification fails closed
with a clear message, and no OTP code ever appears in a response or a log.  SMS is only ever an isolated fake that
captures codes inside the test process (conftest removes any real SMS credentials)."""
import asyncio
import logging

import pytest

from app.models.otp import OTPRecord

UNAVAILABLE = "Phone verification is temporarily unavailable"


def fake_sms(monkeypatch, success=True, provider="TEST_SMS"):
    sent = {}

    async def send(phone_number, otp_code):
        sent[phone_number] = otp_code
        return {"success": success, "provider": provider}
    import app.services.sms_service as sms_service
    monkeypatch.setattr(sms_service, "send_real_sms_otp", send)
    monkeypatch.setattr(sms_service, "sms_configured", lambda: True)
    return sent


# ------------------------------------------------------------------ available methods
def test_password_is_primary_and_only_configured_methods_are_offered(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    assert client.get("/api/auth/methods").json() == {"primary": "password", "password": True, "google": False,
                                                       "phone_otp": False}
    monkeypatch.setenv("FAST2SMS_API_KEY", "your_fast2sms_api_key_here")              # template placeholder
    assert client.get("/api/auth/methods").json()["phone_otp"] is False


def test_configured_google_and_sms_are_reported(client, google_signer, monkeypatch):
    monkeypatch.setenv("FAST2SMS_API_KEY", "isolated-test-value-never-used")          # nothing is sent by /methods
    methods = client.get("/api/auth/methods").json()
    assert methods["google"] is True and methods["phone_otp"] is True and methods["primary"] == "password"


# ------------------------------------------------------------------ password sign-in without SMS
def test_password_login_works_while_phone_verification_is_unavailable(client, db_session):
    reg = client.post("/api/auth/register", json={"email": "no.sms@example.com", "password": "Correct-Horse-3",
                                                  "full_name": "No SMS"})
    assert reg.status_code == 201
    login = client.post("/api/auth/login", json={"email": "no.sms@example.com", "password": "Correct-Horse-3"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "no.sms@example.com"

    res = client.post("/api/auth/otp/send", json={"phone_number": "9822003300"})
    assert res.status_code == 503 and UNAVAILABLE in res.json()["detail"]
    assert db_session.query(OTPRecord).filter(OTPRecord.phone_number == "+919822003300").count() == 0
    assert client.post("/api/auth/login", json={"email": "no.sms@example.com", "password": "wrong"}).status_code == 401


# ------------------------------------------------------------------ exhausted credits and code secrecy
def test_exhausted_sms_credits_fail_closed_without_leaking_the_code(client, db_session, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    sent = fake_sms(monkeypatch, success=False, provider="Fast2SMS")
    res = client.post("/api/auth/otp/send", json={"phone_number": "9822004400"})
    assert res.status_code == 503 and UNAVAILABLE in res.json()["detail"]
    code = sent["+919822004400"]
    assert code not in res.text and code not in caplog.text
    for attempt in (code, "123456", "000000"):
        verify = client.post("/api/auth/otp/verify", json={"phone_number": "9822004400", "otp": attempt})
        assert verify.status_code == 400 and "access_token" not in verify.json()


def test_delivered_code_is_never_returned_or_logged_and_wrong_codes_fail(client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    sent = fake_sms(monkeypatch)
    res = client.post("/api/auth/otp/send", json={"phone_number": "9822005500"})
    assert res.status_code == 200 and res.json()["dev_otp"] is None
    code = sent["+919822005500"]
    wrong = "111111" if code != "111111" else "222222"
    assert client.post("/api/auth/otp/verify", json={"phone_number": "9822005500", "otp": wrong}).status_code == 400
    ok = client.post("/api/auth/otp/verify", json={"phone_number": "9822005500", "otp": code})
    assert ok.status_code == 200 and "access_token" in ok.json()
    assert code not in res.text and code not in caplog.text


def test_sms_service_without_a_provider_sends_nothing_and_logs_no_code(monkeypatch, caplog):
    from app.services import sms_service

    class NoNetwork:
        def __init__(self, *args, **kwargs):
            raise AssertionError("no HTTP client may be created without a provider")
    monkeypatch.setattr(sms_service.httpx, "AsyncClient", NoNetwork)
    caplog.set_level(logging.DEBUG)
    assert sms_service.sms_configured() is False
    assert asyncio.run(sms_service.send_real_sms_otp("9822006600", "482913")) == {"success": False,
                                                                                   "provider": "SIMULATION"}
    assert "482913" not in caplog.text


def test_provider_failure_logs_contain_no_code_or_response_body(monkeypatch, caplog):
    """Exhausted credits at the provider: the real sms_service path, with a fake HTTP client (no network)."""
    from app.services import sms_service

    class Response:
        status_code = 200

        def json(self):
            return {"return": False, "message": ["Insufficient balance for code 731905"], "status_code": 412}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            return Response()
    monkeypatch.setenv("FAST2SMS_API_KEY", "isolated-test-value-never-used")
    monkeypatch.setattr(sms_service.httpx, "AsyncClient", FakeClient)
    caplog.set_level(logging.DEBUG)
    result = asyncio.run(sms_service.send_real_sms_otp("9822007700", "731905"))
    assert result == {"success": False, "provider": "Fast2SMS"}
    assert "731905" not in caplog.text and "Insufficient balance" not in caplog.text


# ------------------------------------------------------------------ demo accounts from seed_data.py
@pytest.mark.parametrize("value", ["", "admin123", "password123", "short-pass", "aaaaaaaaaaaaaaaa", "REPLACE_ME_password1"])
def test_seed_data_refuses_missing_or_weak_demo_passwords(monkeypatch, value):
    import seed_data
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", value)
    with pytest.raises(SystemExit) as error:
        seed_data.seed_password("SEED_ADMIN_PASSWORD")
    assert not value or value not in str(error.value)


def test_seed_data_refuses_before_touching_the_database(monkeypatch):
    import seed_data
    monkeypatch.delenv("SEED_USER_PASSWORD", raising=False)
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "A-private-admin-pass-42")

    def forbidden(*args, **kwargs):
        raise AssertionError("seed_data dropped tables before validating passwords")
    monkeypatch.setattr(seed_data.Base.metadata, "drop_all", forbidden)
    with pytest.raises(SystemExit):
        seed_data.seed()
    monkeypatch.setenv("SEED_USER_PASSWORD", "A-private-user-pass-42")
    assert seed_data.seed_password("SEED_USER_PASSWORD") == "A-private-user-pass-42"


# ------------------------------------------------------------------ authorization is unchanged
def test_protected_actions_still_require_authorization(client, make_user):
    _, user = make_user()
    for method, path, body in [("post", "/api/campaigns", {"title": "x" * 6, "category": "MEDICAL", "goal_amount": 1000,
                                                              "story": "A story long enough for validation."}),
                               ("post", "/api/campaigns/1/payouts", {"amount": 10, "bank_name": "SBI",
                                                                     "ifsc_code": "SBIN0001234", "account_number": "123456789"}),
                               ("get", "/api/admin/flagged", None), ("get", "/api/admin/donations", None),
                               ("post", "/api/admin/campaigns/1/decision", {"decision": "APPROVE"}),
                               ("post", "/api/auth/promote-admin", {"user_id": 1})]:
        call = getattr(client, method)
        kwargs = {"json": body} if body is not None else {}
        assert call(path, **kwargs).status_code == 401, path
        if path.startswith(("/api/admin", "/api/auth/promote-admin")):
            assert call(path, headers=user, **kwargs).status_code == 403, path
    res = client.post("/api/documents/upload", files={"file": ("n.txt", b"note", "text/plain")})
    assert res.status_code == 401
