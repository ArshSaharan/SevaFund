"""Development-only hybrid v4 integration, tested end to end through the FastAPI app.

Real uploads, database, auth, admin, donation and payout endpoints; Gemini is an offline scripted stand-in (no network,
no key); external confirmations are simulated by an admin or trust reviewer recording them.
"""
import ast
import datetime
import json
import uuid
from pathlib import Path

import pytest

from app.models.user import User
from app.schemas.ai import DimensionScores, VerificationResult
from app.services.security import create_access_token, hash_password

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.datetime.utcnow().date()


def d(days: int) -> str:
    return (TODAY + datetime.timedelta(days=days)).strftime("%d/%m/%Y")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")
    import app.services.gemini_api as gemini_api
    import app.services.rag as rag
    monkeypatch.setattr(gemini_api, "post_json", forbidden)
    monkeypatch.setattr(rag, "post_json", forbidden)


@pytest.fixture
def uploads(monkeypatch, tmp_path):
    import app.routers.documents as documents
    import app.services.rag as rag
    monkeypatch.setattr(rag, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def v4(monkeypatch, uploads):
    monkeypatch.setenv("SEVAFUND_DEV_HYBRID_V4", "1")
    monkeypatch.setenv("SEVAFUND_DEV_HYBRID_V4_GEMINI", "mock-approve")
    return monkeypatch


def user(db, role="USER"):
    u = User(email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com", hashed_password=hash_password("pw123456"),
             full_name=f"Test {role}", role=role, is_identity_verified=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u, {"Authorization": f"Bearer {create_access_token({'sub': str(u.id), 'role': u.role})}"}


def upload(client, headers, title, text, doc_type):
    res = client.post("/api/documents/upload", files={"file": (f"{uuid.uuid4().hex}.txt", text.encode(), "text/plain")},
                      data={"doc_type": doc_type, "title": title}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


ESTIMATE = ("Sushruta Hospital, Wardha Road, Nagpur 440015. Ph 0712 555 0199\nEstimate No. SH/EST/26/4471 Date: {issued}\nPatient: Kamala "
            "Bai, 68 F, UHID SH-208813\nProcedure: Left hip hemiarthroplasty\nImplant Rs 75,000; Surgery and OT Rs 55,000; "
            "Ward 4 days Rs 32,000; Medicines Rs 23,000\nTotal estimate Rs 1,85,000. Planned surgery date: {surgery}. "
            "Billing Executive (signed)")
NOTE = ("Sushruta Hospital casualty {seen}. Kamala Bai 68 F. Displaced fracture neck of left femur after a fall at home. "
        "Advised hemiarthroplasty. Dr P. Wankhede MS Ortho")


def create_legit(client, headers, goal=185000):
    docs = [upload(client, headers, "Hospital estimate", ESTIMATE.format(issued=d(-3), surgery=d(7)), "HOSPITAL_ESTIMATE"),
            upload(client, headers, "Orthopaedic note", NOTE.format(seen=d(-4)), "CLINICAL_NOTE")]
    payload = {"title": "Hip surgery for Kamala Bai", "category": "MEDICAL", "goal_amount": goal,
               "story": "Kamala Bai, 68, fractured her left hip. Sushruta Hospital will operate next week.",
               "beneficiary_name": "Kamala Bai", "beneficiary_type": "SELF", "city": "Nagpur", "state": "Maharashtra",
               "proof_documents": docs}
    res = client.post("/api/campaigns", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def create_informal(client, headers):
    docs = [upload(client, headers, "List of items to purchase",
                   "Government Medical College Hospital, Patna. Patient Bhola Prasad 39 M. Items to be purchased before "
                   f"surgery: pedicle screws 6, rods 2. Date {d(-6)}. Unit In-charge", "HOSPITAL_LETTER"),
            upload(client, headers, "Admission slip",
                   f"GMCH Patna. Admitted {d(-7)}. Bhola Prasad 39 M. L1 burst fracture. Planned posterior fixation. "
                   "Dr A. K. Singh", "CLINICAL_NOTE")]
    payload = {"title": "Spine surgery at the government hospital for Bhola", "category": "MEDICAL", "goal_amount": 120000,
               "story": "Bhola Prasad injured his spine. The government hospital operates free but he must buy implants.",
               "beneficiary_name": "Bhola Prasad", "beneficiary_type": "SELF", "city": "Patna", "state": "Bihar",
               "proof_documents": docs}
    res = client.post("/api/campaigns", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def record(client, cid, headers):
    res = client.get(f"/api/dev/hybrid-v4/campaigns/{cid}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def confirm(client, cid, headers, check, outcome="CONFIRMED", source="OFFICIAL_DIRECTORY", **extra):
    return client.post(f"/api/dev/hybrid-v4/campaigns/{cid}/confirmations", headers=headers,
                       json={"check": check, "outcome": outcome, "contact_source": source, **extra})


def confirm_identity_checks(client, cid, headers):
    for check, source in (("BENEFICIARY", "PLATFORM_KYC"), ("INSTITUTION", "OFFICIAL_DIRECTORY"),
                          ("PAYMENT_DESTINATION", "PLATFORM_KYC")):
        assert confirm(client, cid, headers, check, source=source).status_code == 200


def donate(client, cid, amount=5000):
    return client.post(f"/api/campaigns/{cid}/donate", json={"amount": amount, "payment_method": "UPI"})


def payout(client, cid, headers, amount):
    return client.post(f"/api/campaigns/{cid}/payouts", headers=headers,
                       json={"amount": amount, "bank_name": "State Bank of India", "ifsc_code": "SBIN0001234",
                             "account_number": "123456789012"})


def status_of(client, cid):
    return client.get(f"/api/campaigns/{cid}").json()["status"]


# ------------------------------------------------------------------ flag off: production behaviour preserved
def high_score_result(**_):
    return VerificationResult(authenticity_score=95.0, risk_level="LOW", recommendation="AUTO_APPROVE",
                              summary="Mock production result.",
                              dimension_scores=DimensionScores(plausibility=95, specificity=95, red_flag_score=95,
                                                               documentation=95))


@pytest.fixture
def high_score(monkeypatch):
    from app.services.ai_verifier import ai_verifier

    async def fake(**kwargs):
        return high_score_result()
    monkeypatch.setattr(ai_verifier, "verify_campaign_request", fake)


def test_flag_is_off_by_default_and_production_behaviour_is_unchanged(client, db_session, uploads, high_score, monkeypatch):
    monkeypatch.delenv("SEVAFUND_DEV_HYBRID_V4", raising=False)
    from app.services import dev_hybrid_v4_flag
    assert dev_hybrid_v4_flag.enabled() is False and dev_hybrid_v4_flag.gemini_mode() == "off"
    creator, headers = user(db_session)
    campaign = create_legit(client, headers)
    assert campaign["status"] == "PENDING_VERIFICATION"
    assert client.get(f"/api/dev/hybrid-v4/campaigns/{campaign['id']}", headers=headers).status_code == 404
    assert donate(client, campaign["id"]).status_code == 201                      # production: pending accepts donations
    assert client.post(f"/api/campaigns/{campaign['id']}/verify", headers=headers).status_code == 200
    assert status_of(client, campaign["id"]) == "ACTIVE"                           # production: the score publishes
    assert "/api/dev/hybrid-v4/campaigns/{campaign_id}" not in client.get("/openapi.json").json()["paths"]


# ------------------------------------------------------------------ flag on: a score never publishes
def test_high_score_never_publishes_a_campaign(client, db_session, v4, high_score):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    campaign = create_legit(client, headers)
    cid = campaign["id"]
    assert campaign["status"] == "PENDING_VERIFICATION" and campaign["authenticity_score"] == 95.0
    assert client.post(f"/api/campaigns/{cid}/verify", headers=headers).status_code == 200
    assert status_of(client, cid) == "PENDING_VERIFICATION"
    state = record(client, cid, admin)
    assert state["workflow_state"] == "ELIGIBLE_PENDING_CONFIRMATION" and state["automated_decision"] == "APPROVED"
    assert state["required_checks"] == ["BENEFICIARY", "INSTITUTION", "PAYMENT_DESTINATION", "AMOUNT"]
    res = client.post(f"/api/admin/campaigns/{cid}/decision", json={"decision": "APPROVE"}, headers=admin)
    assert res.status_code == 409 and status_of(client, cid) == "PENDING_VERIFICATION"


# ------------------------------------------------------------------ the complete workflow
def test_activation_needs_all_four_independent_confirmations(client, db_session, v4):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    _, reviewer = user(db_session, "TRUST_REVIEWER")
    cid = create_legit(client, headers)["id"]
    assert donate(client, cid).status_code == 400 and payout(client, cid, headers, 1000).status_code == 400
    confirm_identity_checks(client, cid, reviewer)
    state = record(client, cid, admin)
    assert state["workflow_state"] == "ELIGIBLE_PENDING_CONFIRMATION" and state["activation"]["pending_checks"] == ["AMOUNT"]
    assert status_of(client, cid) == "PENDING_VERIFICATION" and donate(client, cid).status_code == 400
    assert confirm(client, cid, reviewer, "AMOUNT", stated_amount_inr=185000).status_code == 200
    state = record(client, cid, admin)
    assert state["campaign_status"] == "ACTIVE" and state["activation"]["activation_valid"]
    assert state["activation"]["independently_confirmed"] == ["AMOUNT", "BENEFICIARY", "INSTITUTION", "PAYMENT_DESTINATION"]
    assert state["activation"]["audit_chain_valid"] and len(state["audit_log"]) >= 7
    assert donate(client, cid, 5000).status_code == 201
    assert payout(client, cid, headers, 5000).status_code == 201


def test_inflated_goal_is_stopped_at_the_amount_check_and_review_cannot_activate(client, db_session, v4):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    confirm_identity_checks(client, cid, admin)
    assert confirm(client, cid, admin, "AMOUNT", stated_amount_inr=120000).status_code == 200    # issuer: Rs 1.2 lakh
    assert status_of(client, cid) == "FLAGGED"
    res = client.post(f"/api/admin/campaigns/{cid}/decision", json={"decision": "APPROVE", "notes": "explained"},
                      headers=admin)
    assert res.status_code == 200 and res.json()["status"] == "PENDING_VERIFICATION"          # cleared, not activated
    assert record(client, cid, admin)["activation"]["pending_checks"] == ["BENEFICIARY", "INSTITUTION",
                                                                          "PAYMENT_DESTINATION", "AMOUNT"]
    assert donate(client, cid).status_code == 400


@pytest.mark.parametrize("attempts", [
    [("BENEFICIARY", "UNREACHABLE", "PLATFORM_KYC", {}), ("INSTITUTION", "INCONCLUSIVE", "OFFICIAL_DIRECTORY", {})],
    [(c, "CONFIRMED", "CAMPAIGN_SUPPLIED", {"stated_amount_inr": 185000})
     for c in ("BENEFICIARY", "INSTITUTION", "PAYMENT_DESTINATION", "AMOUNT")],
    [("AMOUNT", "CONFIRMED", "OFFICIAL_DIRECTORY", {}), ("AMOUNT", "UNREACHABLE", "OFFICIAL_DIRECTORY", {})],
    # labelled "official directory", but the number is printed in the campaign's own estimate -> campaign-supplied
    [("INSTITUTION", "CONFIRMED", "OFFICIAL_DIRECTORY", {"contact_reference": "0712 555 0199"})],
])
def test_missing_or_failed_confirmations_leave_the_campaign_pending(client, db_session, v4, attempts):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    if attempts[0][0] != "BENEFICIARY":
        confirm(client, cid, admin, "BENEFICIARY", source="PLATFORM_KYC")
    for check, outcome, source, extra in attempts:
        assert confirm(client, cid, admin, check, outcome, source, **extra).status_code == 200
    state = record(client, cid, admin)
    assert state["campaign_status"] == "PENDING_VERIFICATION" and not state["activation"]["activated"]
    assert {check for check, *_ in attempts} <= set(state["activation"]["pending_checks"])
    assert donate(client, cid).status_code == 400
    if attempts[0][3].get("contact_reference"):
        assert state["confirmations"][-1]["contact_source"] == "CAMPAIGN_SUPPLIED"


def test_a_contradicted_confirmation_flags_the_campaign(client, db_session, v4):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    assert confirm(client, cid, admin, "PAYMENT_DESTINATION", "CONTRADICTED", "PLATFORM_KYC").status_code == 200
    assert status_of(client, cid) == "FLAGGED" and donate(client, cid).status_code == 400


# ------------------------------------------------------------------ legitimate but incomplete
def test_missing_quotation_cannot_activate_until_assisted_review_and_four_confirmations(client, db_session, v4):
    v4.setenv("SEVAFUND_DEV_HYBRID_V4_GEMINI", "mock-nmi")
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_informal(client, headers)["id"]
    state = record(client, cid, admin)
    assert state["workflow_state"] == "NEEDS_MORE_INFORMATION" and state["manual_route"] == "ASSISTED_COST_CONFIRMATION"
    assert any("caseworker" in r for r in state["information_requests"]) and state["review_basis"] is None
    assert confirm(client, cid, admin, "BENEFICIARY", source="PLATFORM_KYC").status_code == 409   # nothing to confirm yet
    assert client.post(f"/api/admin/campaigns/{cid}/decision", json={"decision": "APPROVE"}, headers=admin).status_code == 409
    assert donate(client, cid).status_code == 400
    assert client.post(f"/api/dev/hybrid-v4/campaigns/{cid}/assisted-cost-review", json={}, headers=headers).status_code == 403
    assert client.post(f"/api/dev/hybrid-v4/campaigns/{cid}/assisted-cost-review", json={}, headers=admin).status_code == 200
    assert status_of(client, cid) == "PENDING_VERIFICATION"
    confirm_identity_checks(client, cid, admin)
    assert status_of(client, cid) == "PENDING_VERIFICATION" and donate(client, cid).status_code == 400
    assert confirm(client, cid, admin, "AMOUNT", stated_amount_inr=118000).status_code == 200
    assert status_of(client, cid) == "ACTIVE" and donate(client, cid).status_code == 201


def test_missing_identity_or_need_gets_no_assisted_route_and_cannot_activate(client, db_session, v4):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    payload = {"title": "Treatment support for Joseph", "category": "MEDICAL", "goal_amount": 48000,
               "story": "Joseph Mathew needs help for an operation. Documents will follow later.",
               "beneficiary_name": "Joseph Mathew", "city": "Thrissur", "state": "Kerala"}
    cid = client.post("/api/campaigns", json=payload, headers=headers).json()["id"]
    state = record(client, cid, admin)
    assert state["workflow_state"] == "NEEDS_MORE_INFORMATION" and state["manual_route"] is None
    assert client.post(f"/api/dev/hybrid-v4/campaigns/{cid}/assisted-cost-review", json={}, headers=admin).status_code == 409
    assert confirm(client, cid, admin, "AMOUNT", stated_amount_inr=48000).status_code == 409
    assert status_of(client, cid) == "PENDING_VERIFICATION" and donate(client, cid).status_code == 400


# ------------------------------------------------------------------ Gemini: offline, never decisive on its own
def test_without_gemini_hybrid_v4_never_approves(client, db_session, v4):
    v4.setenv("SEVAFUND_DEV_HYBRID_V4_GEMINI", "off")
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    assert record(client, cid, admin)["workflow_state"] == "VERIFICATION_ERROR"
    assert status_of(client, cid) == "PENDING_VERIFICATION" and donate(client, cid).status_code == 400
    v4.setenv("SEVAFUND_DEV_HYBRID_V4_GEMINI", "mock-approve")                     # re-verification after the failure
    assert client.post(f"/api/campaigns/{cid}/verify", headers=headers).status_code == 200
    state = record(client, cid, admin)
    assert state["workflow_state"] == "ELIGIBLE_PENDING_CONFIRMATION" and state["previous_records"] == 1


def test_unquoted_gemini_suspicion_is_a_review_referral_never_a_rejection(client, db_session, v4):
    v4.setenv("SEVAFUND_DEV_HYBRID_V4_GEMINI", "mock-flag-unquoted")
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    state = record(client, cid, admin)
    assert state["campaign_status"] == "FLAGGED" and state["review_basis"] == "UNVERIFIED_MODEL_SUSPICION"
    assert {f["source"] for f in state["findings"]} == {"GEMINI_UNVERIFIED"}


def test_conflicting_bank_details_are_flagged_with_evidence(client, db_session, v4):
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    docs = [upload(client, headers, "Hospital estimate", ESTIMATE.format(issued=d(-3), surgery=d(7)), "HOSPITAL_ESTIMATE"),
            upload(client, headers, "Orthopaedic note", NOTE.format(seen=d(-4)), "CLINICAL_NOTE"),
            upload(client, headers, "Hospital bank letter", "Please pay to Account name: Sushruta Hospital A/c No. "
                   "30418877201, SBI.", "LETTER"),
            upload(client, headers, "Donor letter", "Please pay to Account name: Sushruta Hospital A/c No. "
                   "50100234998812, HDFC Bank.", "LETTER")]
    payload = {"title": "Hip surgery for Kamala Bai", "category": "MEDICAL", "goal_amount": 185000,
               "story": "Kamala Bai, 68, fractured her left hip. Sushruta Hospital will operate next week.",
               "beneficiary_name": "Kamala Bai", "city": "Nagpur", "state": "Maharashtra", "proof_documents": docs}
    cid = client.post("/api/campaigns", json=payload, headers=headers).json()["id"]
    state = record(client, cid, admin)
    assert state["campaign_status"] == "FLAGGED" and state["review_basis"] == "DETERMINISTIC_FINDING"
    payment = [f for f in state["findings"] if f["code"] == "PAYMENT_ACCOUNT_CONFLICT"]
    assert payment and len(payment[0]["evidence"]) == 2


# ------------------------------------------------------------------ guards
def test_permissions_self_confirmation_and_goal_changes(client, db_session, v4):
    creator, headers = user(db_session)
    _, other = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    assert confirm(client, cid, other, "BENEFICIARY", source="PLATFORM_KYC").status_code == 403
    assert client.get(f"/api/dev/hybrid-v4/campaigns/{cid}", headers=other).status_code == 403
    creator.role = "ADMIN"                                                          # even an admin creator cannot self-confirm
    db_session.commit()
    assert confirm(client, cid, headers, "BENEFICIARY", source="PLATFORM_KYC").status_code == 403
    creator.role = "USER"
    db_session.commit()
    assert "audit_log" not in record(client, cid, headers)                          # creators see no audit internals
    res = client.put(f"/api/campaigns/{cid}", json={"goal_amount": 250000}, headers=headers)
    assert res.status_code == 409 and client.get(f"/api/campaigns/{cid}").json()["goal_amount"] == 185000


def test_a_tampered_activation_record_freezes_funds(client, db_session, v4):
    from app.models.dev_hybrid_v4 import DevHybridV4Record
    creator, headers = user(db_session)
    _, admin = user(db_session, "ADMIN")
    cid = create_legit(client, headers)["id"]
    confirm_identity_checks(client, cid, admin)
    confirm(client, cid, admin, "AMOUNT", stated_amount_inr=185000)
    assert donate(client, cid).status_code == 201
    row = db_session.query(DevHybridV4Record).filter(DevHybridV4Record.campaign_id == cid).first()
    data = json.loads(row.record_json)
    data["audit"]["entries"][2]["data"]["outcome"] = "CONTRADICTED"
    row.record_json = json.dumps(data)
    db_session.commit()
    res = donate(client, cid)
    assert res.status_code == 400 and "re-check" in res.json()["detail"]


def test_production_and_frozen_modules_do_not_import_the_integration_eagerly():
    """With the flag off nothing loads the integration: production routers import only the tiny flag module."""
    for name in ("campaigns.py", "admin.py", "donations.py", "payouts.py", "dev_hybrid_v4.py"):
        tree = ast.parse((ROOT / "app" / "routers" / name).read_text())
        top_level = {n.module for n in tree.body if isinstance(n, ast.ImportFrom)} | \
                    {a.name for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
        assert "dev_hybrid_v4_integration" not in top_level and "app.models.dev_hybrid_v4" not in top_level, name
    for frozen in ("app/config.py", "app/services/ai_verifier.py"):
        assert "hybrid_v4" not in (ROOT / frozen).read_text()
