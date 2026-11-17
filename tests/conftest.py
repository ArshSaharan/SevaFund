import os
import secrets

# Isolated tests sign tokens with a fresh random key, never the developer's .env key or a public default.
# Set before the application is imported (the app refuses to start without a strong key).
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)

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
