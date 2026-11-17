"""Access control: no unauthenticated demo identity on application routes, and administrator rights only through an
authenticated administrator (never through SECRET_KEY).  Identities come only from the explicit make_user fixture."""
import inspect
import secrets
from pathlib import Path

import jwt as pyjwt
import pytest

from app.models.audit_log import AdminAuditLog
from app.models.campaign import Campaign
from app.models.user import User

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = {"title": "Access control test campaign", "category": "MEDICAL", "goal_amount": 50000.0,
            "story": "A campaign used only to test that creation requires authentication.", "city": "Pune",
            "state": "Maharashtra"}
BAD_TOKENS = [{}, {"Authorization": "Bearer not-a-token"},
              {"Authorization": "Bearer " + pyjwt.encode({"sub": "1", "role": "ADMIN", "iat": 1, "exp": 4102444800},
                                                         secrets.token_urlsafe(48), algorithm="HS256")}]


@pytest.fixture
def uploads(monkeypatch, tmp_path):
    import app.routers.documents as documents
    import app.services.rag as rag
    monkeypatch.setattr(rag, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path)
    return tmp_path


def upload(client, headers):
    return client.post("/api/documents/upload", headers=headers, data={"doc_type": "OTHER", "title": "Note"},
                       files={"file": ("note.txt", b"A short supporting note.", "text/plain")})


# ------------------------------------------------------------------ no unauthenticated demo identity
@pytest.mark.parametrize("headers", BAD_TOKENS)
def test_unauthenticated_users_cannot_create_campaigns(client, db_session, headers):
    before = db_session.query(Campaign).count()
    assert client.post("/api/campaigns", json=CAMPAIGN, headers=headers).status_code == 401
    assert db_session.query(Campaign).count() == before
    assert db_session.query(User).filter(User.email == "organizer@crowdfund-demo.com").first() is None


@pytest.mark.parametrize("headers", BAD_TOKENS)
def test_unauthenticated_users_cannot_upload_documents(client, uploads, headers):
    assert upload(client, headers).status_code == 401
    assert list(uploads.iterdir()) == []


def test_authenticated_users_can_still_create_campaigns_and_upload(client, make_user, uploads):
    user, headers = make_user()
    doc = upload(client, headers)
    assert doc.status_code == 201 and len(list(uploads.iterdir())) == 1
    res = client.post("/api/campaigns", json={**CAMPAIGN, "proof_documents": [doc.json()]}, headers=headers)
    assert res.status_code == 201 and res.json()["creator_id"] == user.id


def test_no_application_code_provides_a_demo_identity():
    from app.services import auth_dependencies
    assert not hasattr(auth_dependencies, "get_current_user_or_demo")
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "get_current_user_or_demo" not in text and "crowdfund-demo.com" not in text, path


# ------------------------------------------------------------------ administrator promotion
def test_users_cannot_promote_themselves(client, make_user, db_session):
    from app.config import settings
    for role in ("USER", "TRUST_REVIEWER"):
        user, headers = make_user(role)
        res = client.post("/api/auth/promote-admin", headers=headers,
                          json={"user_id": user.id, "secret_key": settings.SECRET_KEY})
        assert res.status_code == 403
        db_session.refresh(user)
        assert user.role == role
    target, _ = make_user()
    assert client.post("/api/auth/promote-admin", json={"user_id": target.id, "secret_key": settings.SECRET_KEY}).status_code == 401
    assert db_session.query(AdminAuditLog).filter(AdminAuditLog.target_id == target.id,
                                                  AdminAuditLog.action == "USER_PROMOTED_TO_ADMIN").count() == 0


def test_only_an_authenticated_administrator_can_promote_and_it_is_audited(client, make_user, db_session):
    target, _ = make_user()
    admin, admin_headers = make_user("ADMIN")
    res = client.post("/api/auth/promote-admin", headers=admin_headers, json={"user_id": target.id, "reason": "on-call"})
    assert res.status_code == 200 and res.json()["role"] == "ADMIN"
    log = db_session.query(AdminAuditLog).filter(AdminAuditLog.target_id == target.id,
                                                 AdminAuditLog.action == "USER_PROMOTED_TO_ADMIN").one()
    assert log.admin_id == admin.id and log.target_type == "USER" and log.previous_status == "USER" and log.reason == "on-call"
    assert client.post("/api/auth/promote-admin", headers=admin_headers, json={"user_id": 999999}).status_code == 404


def test_signing_key_is_not_an_administrator_credential():
    import ast
    import textwrap
    from app.routers import auth
    from app.schemas.user import MakeAdminRequest
    tree = ast.parse(textwrap.dedent(inspect.getsource(auth.promote_user_to_admin)))
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not {"SECRET_KEY", "secret_key", "settings", "JWT_SECRET"} & used          # code, not the docstring
    assert "require_admin" in used
    assert "secret_key" not in MakeAdminRequest.model_fields
