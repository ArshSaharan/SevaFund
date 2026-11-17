"""Razorpay payment verification: no donation is recorded without a verified, captured payment of a stored order.

Payments are simulated only by the isolated fake_razorpay fixture (conftest.py); application code has no simulation.
No test makes a real Razorpay or SMS request (conftest blocks httpx in both services) or sees a real .env credential.
"""
import hashlib
import hmac
import importlib
import json
import secrets
from pathlib import Path

import pytest

from app.models.campaign import Campaign
from app.models.donation import Donation
from app.models.payment_order import PaymentOrder

ROOT = Path(__file__).resolve().parents[1]
payments = importlib.import_module("app.services.payment_service")


@pytest.fixture
def campaign(client, make_user):
    _, organiser = make_user()
    res = client.post("/api/campaigns", headers=organiser, json={
        "title": "Payment verification test campaign", "category": "MEDICAL", "goal_amount": 100000.0,
        "story": "A campaign used only to test payment verification.", "city": "Pune", "state": "Maharashtra"})
    assert res.status_code == 201
    return res.json()["id"]


def create_order(client, campaign_id, amount=1000.0, tip=0.0):
    res = client.post("/api/donations/create-order", json={"campaign_id": campaign_id, "amount": amount, "tip_amount": tip})
    assert res.status_code == 200, res.text
    return res.json()["order_id"]


def donate(client, campaign_id, amount=1000.0, tip=0.0, **gateway):
    return client.post(f"/api/campaigns/{campaign_id}/donate",
                       json={"amount": amount, "tip_amount": tip, "payment_method": "UPI", **gateway})


def state(db, campaign_id):
    db.expire_all()
    c = db.query(Campaign).filter(Campaign.id == campaign_id).one()
    return c.current_amount, c.donor_count, db.query(Donation).filter(Donation.campaign_id == campaign_id).count()


# ------------------------------------------------------------------ forged confirmations are rejected
@pytest.mark.parametrize("signature", ["mock_signature", "mock_", "sig_demo", "sig_mock_signature", "sig_",
                                       "0" * 64, "f" * 64, "", "not-hex-" * 8])
def test_fake_or_invalid_signatures_are_rejected(client, db_session, fake_razorpay, campaign, signature):
    order_id = create_order(client, campaign)
    paid = fake_razorpay.pay(order_id)
    res = donate(client, campaign, gateway_order_id=order_id, gateway_payment_id=paid["gateway_payment_id"],
                 gateway_signature=signature)
    assert res.status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0)


def test_signature_from_another_secret_is_rejected(client, db_session, fake_razorpay, campaign):
    order_id = create_order(client, campaign)
    paid = fake_razorpay.pay(order_id)
    forged = payments.payment_signature(order_id, paid["gateway_payment_id"], secrets.token_hex(24))
    assert donate(client, campaign, **{**paid, "gateway_signature": forged}).status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0)


@pytest.mark.parametrize("missing", ["all", "gateway_order_id", "gateway_payment_id", "gateway_signature"])
def test_a_donation_without_a_complete_payment_is_rejected(client, db_session, fake_razorpay, campaign, missing):
    paid = fake_razorpay.pay(create_order(client, campaign))
    body = {} if missing == "all" else {k: v for k, v in paid.items() if k != missing}
    assert donate(client, campaign, **body).status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0)


def test_wrong_or_unknown_order_ids_are_rejected(client, db_session, fake_razorpay, campaign, make_user):
    _, organiser = make_user()
    other = client.post("/api/campaigns", headers=organiser, json={
        "title": "Another campaign for order checks", "category": "MEDICAL", "goal_amount": 5000.0,
        "story": "Used to check that orders belong to their campaign.", "city": "Pune", "state": "Maharashtra"}).json()["id"]
    paid_other = fake_razorpay.pay(create_order(client, other))                 # a genuine payment for ANOTHER campaign
    assert donate(client, campaign, **paid_other).status_code == 400
    paid = fake_razorpay.pay(create_order(client, campaign))
    unknown = "order_" + secrets.token_hex(7)                                   # never created by this server
    forged = payments.payment_signature(unknown, paid["gateway_payment_id"], fake_razorpay.key_secret)
    assert donate(client, campaign, gateway_order_id=unknown, gateway_payment_id=paid["gateway_payment_id"],
                  gateway_signature=forged).status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0) and state(db_session, other) == (0.0, 0, 0)


def test_incorrect_amounts_are_rejected(client, db_session, fake_razorpay, campaign):
    order_id = create_order(client, campaign, amount=1000.0)
    paid = fake_razorpay.pay(order_id)
    assert donate(client, campaign, amount=100000.0, **paid).status_code == 400   # claims more than was paid
    assert donate(client, campaign, amount=1000.0, tip=50.0, **paid).status_code == 400
    underpaid = fake_razorpay.pay(create_order(client, campaign, amount=1000.0), amount_paise=100)   # gateway: Rs 1
    assert donate(client, campaign, amount=1000.0, **underpaid).status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0)


@pytest.mark.parametrize("status, currency", [("authorized", "INR"), ("failed", "INR"), ("created", "INR"),
                                              ("captured", "USD")])
def test_payment_status_and_currency_must_match(client, db_session, fake_razorpay, campaign, status, currency):
    paid = fake_razorpay.pay(create_order(client, campaign), status=status, currency=currency)
    assert donate(client, campaign, **paid).status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0)


def test_non_inr_orders_are_refused(client, fake_razorpay, campaign):
    res = client.post("/api/donations/create-order", json={"campaign_id": campaign, "amount": 10.0, "currency": "USD"})
    assert res.status_code == 400


# ------------------------------------------------------------------ duplicates
def test_duplicate_confirmations_create_one_donation(client, db_session, fake_razorpay, campaign):
    paid = fake_razorpay.pay(create_order(client, campaign, amount=1000.0))
    assert donate(client, campaign, **paid).status_code == 201
    for _ in range(3):
        assert donate(client, campaign, **paid).status_code == 409
    assert state(db_session, campaign) == (1000.0, 1, 1)
    order = db_session.query(PaymentOrder).filter(PaymentOrder.gateway_order_id == paid["gateway_order_id"]).one()
    assert order.status == "PAID" and order.gateway_payment_id == paid["gateway_payment_id"] and order.donation_id


def test_a_second_payment_for_an_already_paid_order_is_not_recorded(client, db_session, fake_razorpay, campaign):
    order_id = create_order(client, campaign, amount=1000.0)
    assert donate(client, campaign, **fake_razorpay.pay(order_id)).status_code == 201
    assert donate(client, campaign, **fake_razorpay.pay(order_id)).status_code == 409
    assert state(db_session, campaign) == (1000.0, 1, 1)


# ------------------------------------------------------------------ fail closed
def test_missing_credentials_fail_closed(client, db_session, campaign):
    res = client.post("/api/donations/create-order", json={"campaign_id": campaign, "amount": 1000.0})
    assert res.status_code == 503
    assert db_session.query(PaymentOrder).filter(PaymentOrder.campaign_id == campaign).count() == 0
    body = {"gateway_order_id": "order_" + "a" * 14, "gateway_payment_id": "pay_" + "b" * 14, "gateway_signature": "c" * 64}
    assert donate(client, campaign, **body).status_code == 503
    assert state(db_session, campaign) == (0.0, 0, 0)


@pytest.mark.parametrize("key_id, secret", [("rzp_test_sevafund_demo", "mock_razorpay_secret"), ("", ""),
                                            ("rzp_test_realistic", ""), ("rzp_test_realistic", "your_razorpay_secret"),
                                            ("not_a_key", "a-real-looking-secret")])
def test_demo_or_placeholder_credentials_are_not_configuration(key_id, secret, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", key_id)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", secret)
    assert payments.razorpay_credentials() is None
    with pytest.raises(payments.PaymentUnavailable):
        payments.get_gateway()


def test_credentials_removed_after_ordering_fail_closed(client, db_session, fake_razorpay, campaign, monkeypatch):
    paid = fake_razorpay.pay(create_order(client, campaign))
    from app.config import settings
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    assert donate(client, campaign, **paid).status_code == 503
    assert state(db_session, campaign) == (0.0, 0, 0)


# ------------------------------------------------------------------ success
def test_successful_simulated_payment_is_recorded_once_with_verified_details(client, db_session, fake_razorpay, campaign):
    order_id = create_order(client, campaign, amount=2500.0, tip=100.0)
    order = db_session.query(PaymentOrder).filter(PaymentOrder.gateway_order_id == order_id).one()
    assert order.amount_paise == 260000 and order.currency == "INR" and order.status == "CREATED"
    paid = fake_razorpay.pay(order_id)
    res = donate(client, campaign, amount=2500.0, tip=100.0, donor_pan="ABCDE1234F", **paid)
    assert res.status_code == 201
    receipt = res.json()
    assert receipt["gateway_order_id"] == order_id and receipt["gateway_payment_id"] == paid["gateway_payment_id"]
    assert receipt["total_charged"] == 2600.0 and receipt["currency"] == "INR"
    assert state(db_session, campaign) == (2500.0, 1, 1)
    assert fake_razorpay.fetched == [paid["gateway_payment_id"]]               # status confirmed server-side


# ------------------------------------------------------------------ webhook
def signed(body: dict, secret: str):
    raw = json.dumps(body).encode()
    return raw, {"X-Razorpay-Signature": hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(),
                 "Content-Type": "application/json"}


def captured_event(order_id, payment_id, amount, currency="INR", status="captured"):
    return {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": payment_id, "order_id": order_id, "amount": amount, "currency": currency, "status": status,
        "email": "donor@example.com", "notes": {}}}}}


def test_webhook_fails_closed_and_verifies_signatures(client, db_session, fake_razorpay, campaign, monkeypatch):
    order_id = create_order(client, campaign, amount=750.0)
    payment_id = "pay_" + secrets.token_hex(7)
    event = captured_event(order_id, payment_id, 75000)
    raw, headers = signed(event, "whsec-isolated-test")
    assert client.post("/api/donations/webhook", content=raw, headers=headers).status_code == 503   # no secret set
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "whsec-isolated-test")
    assert client.post("/api/donations/webhook", content=raw, headers={"Content-Type": "application/json"}).status_code == 400
    bad_raw, bad_headers = signed(event, "another-secret")
    assert client.post("/api/donations/webhook", content=bad_raw, headers=bad_headers).status_code == 400
    wrong_amount_raw, wrong_amount_headers = signed(captured_event(order_id, payment_id, 1), "whsec-isolated-test")
    assert client.post("/api/donations/webhook", content=wrong_amount_raw, headers=wrong_amount_headers).status_code == 400
    assert state(db_session, campaign) == (0.0, 0, 0)
    ok = client.post("/api/donations/webhook", content=raw, headers=headers)
    assert ok.status_code == 200 and ok.json() == {"status": "recorded"}
    again = client.post("/api/donations/webhook", content=raw, headers=headers)
    assert again.status_code == 200 and again.json() == {"status": "duplicate"}
    assert state(db_session, campaign) == (750.0, 1, 1)


def test_checkout_confirmation_and_webhook_record_one_donation(client, db_session, fake_razorpay, campaign, monkeypatch):
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "whsec-isolated-test")
    paid = fake_razorpay.pay(create_order(client, campaign, amount=500.0))
    assert donate(client, campaign, amount=500.0, **paid).status_code == 201
    raw, headers = signed(captured_event(paid["gateway_order_id"], paid["gateway_payment_id"], 50000), "whsec-isolated-test")
    assert client.post("/api/donations/webhook", content=raw, headers=headers).json() == {"status": "duplicate"}
    assert state(db_session, campaign) == (500.0, 1, 1)


# ------------------------------------------------------------------ isolation
def test_tests_never_make_real_razorpay_or_sms_requests(monkeypatch, caplog):
    gateway = payments.RazorpayGateway("rzp_test_isolationcheck", secrets.token_hex(16))
    with pytest.raises(AssertionError, match="must not call external services"):
        gateway.create_order(100, "INR", "rcpt", {})
    with pytest.raises(AssertionError, match="must not call external services"):
        gateway.fetch_payment("pay_" + "a" * 14)
    import asyncio
    import logging
    from app.services import sms_service
    monkeypatch.setenv("FAST2SMS_API_KEY", "isolation-check-value")
    caplog.set_level(logging.ERROR)
    # sms_service catches every exception and reports a failed send; the blocked call shows up in the log.
    assert asyncio.run(sms_service.send_real_sms_otp("9822008800", "123456")) == {"success": False, "provider": "Fast2SMS"}
    assert "Failed to send SMS via Fast2SMS: AssertionError" in caplog.text


def test_no_real_credential_from_the_local_env_file_reaches_tests():
    import os
    import re
    from app.config import settings
    env_file = ROOT / ".env"
    credential = re.compile(r"KEY|SECRET|TOKEN|SID|PASSWORD|CLIENT_ID|FROM_PHONE", re.I)
    for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "GEMINI_API_KEY", "GOOGLE_CLIENT_ID"):
        assert not getattr(settings, name, ""), name                  # blanked or replaced for every test
    if not env_file.exists():
        pytest.skip("no local .env in this checkout")
    real = {}
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            name, value = name.strip(), value.strip().strip('"').strip("'")
            if credential.search(name) and len(value) >= 8:
                real[name] = hashlib.sha256(value.encode()).hexdigest()   # compared by hash; never printed
    leaked = [n for n, h in real.items() if hashlib.sha256(os.environ.get(n, "").encode()).hexdigest() == h
              or hashlib.sha256(str(getattr(settings, n, "")).encode()).hexdigest() == h]
    assert leaked == []
