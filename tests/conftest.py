import os
import re
import secrets
from pathlib import Path

# ------------------------------------------------------------------------------------------------------------------
# Test isolation from the developer's .env, set BEFORE the application is imported.  app/config.py calls
# load_dotenv(), which never overrides variables that are already set, so blanking them here means no real credential
# from .env reaches the test process: no real Gemini, SMS, Google, Razorpay or seed-account values.
# ------------------------------------------------------------------------------------------------------------------
CREDENTIAL_NAME = re.compile(r"KEY|SECRET|TOKEN|SID|PASSWORD|CLIENT_ID|FROM_PHONE", re.I)
_KNOWN_CREDENTIALS = ("GEMINI_API_KEY", "FAST2SMS_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                      "TWILIO_FROM_PHONE", "GOOGLE_CLIENT_ID", "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET",
                      "RAZORPAY_WEBHOOK_SECRET", "SEED_USER_PASSWORD", "SEED_ADMIN_PASSWORD")
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
_names = set(_KNOWN_CREDENTIALS)
if _ENV_FILE.exists():
    _names |= {line.split("=", 1)[0].strip().removeprefix("export ").strip()
               for line in _ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
               if "=" in line and not line.lstrip().startswith("#")}
for _name in sorted(n for n in _names if CREDENTIAL_NAME.search(n)):
    os.environ[_name] = ""
# Isolated tests sign tokens with a fresh random key, never the developer's .env key or a public default.
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["DATABASE_URL"] = "sqlite:///./test_crowdfund.db"     # the application engine never opens crowdfund.db

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_crowdfund.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def no_live_gemini(monkeypatch):
    """Tests must never spend the real Gemini quota; force the local fallback."""
    from app.config import settings
    from app.services.ai_verifier import ai_verifier
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(ai_verifier, "api_key", "")
    from app.services.ai_assistant import ai_assistant
    monkeypatch.setattr(ai_assistant, "api_key", "")


class _ExternalHTTPBlocked:
    """Replaces httpx inside the SMS and payment services during tests: any request fails the test immediately.
    Exception classes (httpx.HTTPError ...) are passed through so error handling still works."""
    _REQUESTS = {"post", "get", "put", "patch", "delete", "request", "stream", "Client", "AsyncClient"}

    def __getattr__(self, name):
        import httpx
        if name in self._REQUESTS:
            def refuse(*args, **kwargs):
                raise AssertionError(f"tests must not call external services (httpx.{name})")
            return refuse
        return getattr(httpx, name)


@pytest.fixture(autouse=True)
def no_real_sms_or_payment_credentials(monkeypatch):
    """Tests never use real SMS or payment credentials and never make real SMS or Razorpay requests.  SMS providers
    and Razorpay are unconfigured (payments fail closed) unless a test installs an isolated fake (fake_razorpay, or a
    fake SMS sender that captures codes inside the test process)."""
    for name in ("FAST2SMS_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_PHONE",
                 "RAZORPAY_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    from app.config import settings
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    import importlib
    payment_service = importlib.import_module("app.services.payment_service")   # the module, not the exported object
    import app.services.sms_service as sms_service
    monkeypatch.setattr(payment_service, "httpx", _ExternalHTTPBlocked())
    monkeypatch.setattr(sms_service, "httpx", _ExternalHTTPBlocked())


class FakeRazorpay:
    """Isolated stand-in for Razorpay's servers, inside the test process only.  It creates orders, simulates a
    checkout payment and signs it with a per-test secret exactly as Razorpay does; it never contacts Razorpay."""

    def __init__(self):
        self.key_id = "rzp_test_isolatedfixture"
        self.key_secret = secrets.token_hex(24)
        self.orders, self.payments, self.fetched = {}, {}, []

    # --- the server-side gateway interface used by app.services.payment_service
    def create_order(self, amount_paise, currency, receipt, notes):
        order_id = "order_" + secrets.token_hex(7)
        self.orders[order_id] = {"id": order_id, "amount": amount_paise, "currency": currency, "receipt": receipt,
                                 "notes": notes, "status": "created"}
        return dict(self.orders[order_id])

    def fetch_payment(self, payment_id):
        from app.services.payment_service import PaymentRejected
        self.fetched.append(payment_id)
        if payment_id not in self.payments:
            raise PaymentRejected("Razorpay has no such payment.")
        return dict(self.payments[payment_id])

    # --- the donor's checkout, simulated
    def pay(self, order_id, amount_paise=None, currency="INR", status="captured"):
        from app.services.payment_service import payment_signature
        payment_id = "pay_" + secrets.token_hex(7)
        order = self.orders[order_id]
        self.payments[payment_id] = {"id": payment_id, "order_id": order_id, "status": status, "currency": currency,
                                     "amount": order["amount"] if amount_paise is None else amount_paise}
        return {"gateway_order_id": order_id, "gateway_payment_id": payment_id,
                "gateway_signature": payment_signature(order_id, payment_id, self.key_secret)}

    def checkout(self, client, campaign_id, amount, tip=0.0, **donation_fields):
        """create-order -> simulated payment -> /donate.  Returns the first non-200 response, or /donate's."""
        order = client.post("/api/donations/create-order", json={"campaign_id": campaign_id, "amount": amount,
                                                                  "tip_amount": tip})
        if order.status_code != 200:
            return order
        paid = self.pay(order.json()["order_id"])
        return client.post(f"/api/campaigns/{campaign_id}/donate",
                           json={"amount": amount, "tip_amount": tip, "payment_method": "UPI", **donation_fields, **paid})


@pytest.fixture
def fake_razorpay(monkeypatch):
    """Test-only Razorpay: configured test credentials plus the in-process FakeRazorpay gateway."""
    from app.config import settings
    import importlib
    payment_service = importlib.import_module("app.services.payment_service")   # the module, not the exported object
    fake = FakeRazorpay()
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", fake.key_id)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", fake.key_secret)

    def gateway():
        if not payment_service.razorpay_credentials():
            raise payment_service.PaymentUnavailable("Online payments are not configured on this server.")
        return fake
    monkeypatch.setattr(payment_service, "get_gateway", gateway)
    return fake


@pytest.fixture
def make_user(db_session):
    """Explicit offline test fixture: creates a user directly in the test database and returns (user, auth headers).
    This is the only place tests obtain an identity without going through a login route."""
    import uuid
    from app.models.user import User
    from app.services.security import create_access_token, hash_password

    def _make(role="USER", email=None):
        user = User(email=email or f"{role.lower()}-{uuid.uuid4().hex[:10]}@test.local",
                    hashed_password=hash_password("Test-Only-Password-1"), full_name=f"Test {role.title()}", role=role,
                    is_identity_verified=True)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user, {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role})}"}
    return _make


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class _GoogleSigner:
    """Signs Google-style ID tokens with an isolated test RSA key.  Verification is google-auth's real code."""
    CLIENT_ID = "sevafund-test-client.apps.googleusercontent.com"

    def __init__(self):
        import datetime
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        def keypair():
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
            return key, pem

        self.key, self.key_pem = keypair()
        self.forger_key, self.forger_pem = keypair()          # an attacker's key, never published as Google's
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "isolated-test-google-certs")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=1)).sign(self.key, hashes.SHA256()))
        self.kid = "isolated-test-kid"
        self.certs = {self.kid: cert.public_bytes(serialization.Encoding.PEM).decode()}

    def token(self, email="user@gmail.com", sub="google-sub-1", aud=None, iss="https://accounts.google.com",
              expires_in=3600, email_verified=True, forged=False, algorithm="RS256"):
        import time
        import jwt as pyjwt
        now = int(time.time())
        claims = {"iss": iss, "aud": aud or self.CLIENT_ID, "sub": sub, "email": email,
                  "email_verified": email_verified, "iat": now - 30, "exp": now + expires_in, "name": "Test User"}
        if algorithm == "none":
            return pyjwt.encode(claims, None, algorithm="none", headers={"kid": self.kid})
        return pyjwt.encode(claims, self.forger_pem if forged else self.key_pem, algorithm=algorithm,
                            headers={"kid": self.kid})


@pytest.fixture
def google_signer(monkeypatch):
    """Configure an isolated Google client ID and serve the test certificate instead of Google's endpoint."""
    import json
    from app.services import security

    signer = _GoogleSigner()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", signer.CLIENT_ID)

    class _Response:
        status = 200
        headers = {}
        data = json.dumps(signer.certs).encode("utf-8")

    def fake_certificate_request(url, method="GET", **kwargs):
        return _Response()

    monkeypatch.setattr(security, "_google_request", lambda: fake_certificate_request)
    return signer
