"""Razorpay payments: orders stored server-side, payments verified before any donation is recorded.

Rules (all fail closed):
  * Orders are created only through Razorpay with configured credentials, and stored in payment_orders.  There is no
    mock or "seamless" order in application code.
  * A donation is recorded only for a stored order of the same campaign, after: the Razorpay signature
    HMAC-SHA256(key_secret, "order_id|payment_id") verifies; the donation amount plus tip equals the order amount;
    the currency is INR; and Razorpay reports the payment as captured for that order, amount and currency.
  * Each order, and each Razorpay payment, is recorded at most once (atomic claim of the order row).
  * Webhooks require RAZORPAY_WEBHOOK_SECRET and a valid X-Razorpay-Signature over the raw body.
Automated tests replace the gateway with an isolated fake (tests/conftest.py); application code has no simulation.
"""
import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.campaign import Campaign
from app.models.donation import Donation
from app.models.payment_order import PaymentOrder
from app.schemas.donation import DonationCreate

logger = logging.getLogger(__name__)

RAZORPAY_API = "https://api.razorpay.com/v1"
CURRENCY = "INR"
ORDER_ID = re.compile(r"order_[A-Za-z0-9]{6,40}")
PAYMENT_ID = re.compile(r"pay_[A-Za-z0-9]{6,40}")
SIGNATURE = re.compile(r"[0-9a-f]{64}")
_NOT_CONFIGURED_KEY_IDS = {"rzp_test_sevafund_demo"}
_NOT_CONFIGURED_SECRETS = {"mock_razorpay_secret"}
_PLACEHOLDER = re.compile(r"^(your|replace|change|example|xxx|<)", re.I)


class PaymentUnavailable(Exception):
    """Payments cannot be processed securely right now (missing credentials or gateway unavailable)."""


class PaymentRejected(Exception):
    """The payment could not be verified; nothing is recorded."""


class PaymentAlreadyRecorded(Exception):
    """This order or payment has already been recorded as a donation."""


def razorpay_credentials() -> Optional[Tuple[str, str]]:
    key_id = (settings.RAZORPAY_KEY_ID or "").strip()
    secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    if not key_id.startswith(("rzp_test_", "rzp_live_")) or key_id in _NOT_CONFIGURED_KEY_IDS:
        return None
    if not secret or secret in _NOT_CONFIGURED_SECRETS or _PLACEHOLDER.search(secret):
        return None
    return key_id, secret


def webhook_secret() -> Optional[str]:
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret or secret in _NOT_CONFIGURED_SECRETS or _PLACEHOLDER.search(secret):
        return None
    return secret


def payment_signature(order_id: str, payment_id: str, key_secret: str) -> str:
    return hmac.new(key_secret.encode("utf-8"), f"{order_id}|{payment_id}".encode("utf-8"), hashlib.sha256).hexdigest()


class RazorpayGateway:
    """Server-to-server Razorpay API calls.  Tests replace get_gateway() with an isolated fake."""

    def __init__(self, key_id: str, key_secret: str):
        self.key_id, self.key_secret = key_id, key_secret

    def create_order(self, amount_paise: int, currency: str, receipt: str, notes: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{RAZORPAY_API}/orders", auth=(self.key_id, self.key_secret), timeout=10.0,
                              json={"amount": amount_paise, "currency": currency, "receipt": receipt, "notes": notes})
        except httpx.HTTPError as exc:
            raise PaymentUnavailable("Razorpay could not be reached.") from exc
        if resp.status_code not in (200, 201):
            logger.warning("Razorpay order creation failed (HTTP %s)", resp.status_code)
            raise PaymentUnavailable("Razorpay could not create the payment order.")
        return resp.json()

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{RAZORPAY_API}/payments/{payment_id}", auth=(self.key_id, self.key_secret), timeout=10.0)
        except httpx.HTTPError as exc:
            raise PaymentUnavailable("Razorpay could not be reached to confirm the payment.") from exc
        if resp.status_code == 404:
            raise PaymentRejected("Razorpay has no such payment.")
        if resp.status_code != 200:
            logger.warning("Razorpay payment lookup failed (HTTP %s)", resp.status_code)
            raise PaymentUnavailable("Razorpay could not confirm the payment.")
        return resp.json()


def get_gateway() -> RazorpayGateway:
    credentials = razorpay_credentials()
    if not credentials:
        raise PaymentUnavailable("Online payments are not configured on this server.")
    return RazorpayGateway(*credentials)


def _paise(amount: float) -> int:
    return int(round(amount * 100))


class PaymentService:
    @staticmethod
    def calculate_fees(amount: float, tip: float = 0.0, payment_method: str = "UPI") -> Tuple[float, float, float]:
        """
        Calculates Indian payment gateway fee (Razorpay/Cashfree standard) and net funds.
        - UPI: 0% or nominal fee
        - Cards/Netbanking: 2% + 18% GST on gateway fee (~2.36% total)
        - Platform fee: 0% (voluntary donor tip model like Milaap/Ketto)
        """
        method = (payment_method or "UPI").upper()
        if method == "UPI":
            fee = round(settings.UPI_FIXED_FEE_INR, 2)
        else:
            base_fee = amount * settings.GATEWAY_FEE_PERCENTAGE
            gst_on_fee = base_fee * settings.GATEWAY_GST_PERCENTAGE
            fee = round(base_fee + gst_on_fee, 2)

        net = round(amount - fee, 2)
        total_charged = round(amount + tip, 2)
        return fee, net, total_charged

    @staticmethod
    def create_gateway_order(db: Session, campaign: Campaign, amount: float, tip: float = 0.0) -> Dict[str, Any]:
        """Create a Razorpay order for amount + tip and store it.  Fails closed without credentials."""
        gateway = get_gateway()
        amount_paise = _paise(amount + tip)
        receipt = f"rcpt_{campaign.id}_{uuid.uuid4().hex[:8]}"
        data = gateway.create_order(amount_paise, CURRENCY, receipt,
                                    {"campaign_id": str(campaign.id), "campaign_title": campaign.title[:30]})
        order_id = str(data.get("id") or "")
        if not ORDER_ID.fullmatch(order_id) or data.get("amount") != amount_paise or data.get("currency") != CURRENCY:
            raise PaymentUnavailable("Razorpay returned an inconsistent order.")
        db.add(PaymentOrder(gateway_order_id=order_id, campaign_id=campaign.id, amount_paise=amount_paise,
                            currency=CURRENCY, receipt=receipt, status="CREATED"))
        db.commit()
        return {"order_id": order_id, "amount": amount_paise, "currency": CURRENCY, "key_id": gateway.key_id,
                "campaign_id": campaign.id, "campaign_title": campaign.title,
                "beneficiary_name": campaign.beneficiary_name}

    @staticmethod
    def _claim_and_record(db: Session, campaign: Campaign, order: PaymentOrder, payment_id: str,
                          donation_in: DonationCreate, donor_id: Optional[int], signature: Optional[str]) -> Donation:
        """Atomically mark the order PAID for this payment, then record exactly one donation."""
        if db.query(PaymentOrder).filter(PaymentOrder.gateway_payment_id == payment_id).first() is not None or \
                db.query(Donation).filter(Donation.gateway_payment_id == payment_id).first() is not None:
            raise PaymentAlreadyRecorded("This payment has already been recorded.")
        claimed = (db.query(PaymentOrder)
                   .filter(PaymentOrder.id == order.id, PaymentOrder.status == "CREATED")
                   .update({"status": "PAID", "gateway_payment_id": payment_id,
                            "paid_at": datetime.datetime.utcnow()}, synchronize_session=False))
        if claimed != 1:
            db.rollback()
            raise PaymentAlreadyRecorded("This payment has already been recorded.")

        fee, net, _ = PaymentService.calculate_fees(donation_in.amount, donation_in.tip_amount, donation_in.payment_method)
        receipt_80g = None
        if donation_in.donor_pan and len(donation_in.donor_pan.strip()) == 10:
            receipt_80g = f"80G-{datetime.datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}"
        donation = Donation(
            campaign_id=campaign.id,
            donor_id=donor_id,
            donor_name=donation_in.donor_name or "Kind Supporter",
            donor_email=donation_in.donor_email,
            donor_phone=donation_in.donor_phone,
            donor_pan=donation_in.donor_pan.upper() if donation_in.donor_pan else None,
            amount=round(donation_in.amount, 2),
            tip_amount=round(donation_in.tip_amount, 2),
            fee_amount=fee,
            net_amount=max(0.0, net),
            currency=CURRENCY,
            payment_method=donation_in.payment_method or "RAZORPAY",
            upi_id=donation_in.upi_id,
            tax_exemption_80g_number=receipt_80g,
            support_message=donation_in.support_message,
            is_anonymous=donation_in.is_anonymous,
            payment_status="COMPLETED",
            transaction_ref=f"TXN-IN-{datetime.datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            gateway_order_id=order.gateway_order_id,
            gateway_payment_id=payment_id,
            gateway_signature=signature,
        )
        db.add(donation)
        db.flush()
        db.query(PaymentOrder).filter(PaymentOrder.id == order.id).update({"donation_id": donation.id},
                                                                          synchronize_session=False)
        campaign.current_amount = round(campaign.current_amount + donation_in.amount, 2)
        campaign.donor_count += 1
        db.commit()
        db.refresh(donation)
        db.refresh(campaign)
        return donation

    @staticmethod
    def record_verified_donation(db: Session, campaign: Campaign, donation_in: DonationCreate,
                                 donor_id: Optional[int] = None) -> Donation:
        """Record a donation only for a verified, captured Razorpay payment of a stored order of this campaign."""
        order_id = (donation_in.gateway_order_id or "").strip()
        payment_id = (donation_in.gateway_payment_id or "").strip()
        signature = (donation_in.gateway_signature or "").strip()
        if not (order_id and payment_id and signature):
            raise PaymentRejected("A completed Razorpay payment (order, payment and signature) is required.")
        if not (ORDER_ID.fullmatch(order_id) and PAYMENT_ID.fullmatch(payment_id) and SIGNATURE.fullmatch(signature)):
            raise PaymentRejected("Payment signature verification failed.")
        gateway = get_gateway()                                       # fails closed without credentials
        order = db.query(PaymentOrder).filter(PaymentOrder.gateway_order_id == order_id).first()
        if order is None or order.campaign_id != campaign.id:
            raise PaymentRejected("This payment order does not belong to this campaign.")
        if not hmac.compare_digest(payment_signature(order_id, payment_id, gateway.key_secret), signature):
            raise PaymentRejected("Payment signature verification failed.")
        if order.status != "CREATED":
            raise PaymentAlreadyRecorded("This payment has already been recorded.")
        if _paise(donation_in.amount + donation_in.tip_amount) != order.amount_paise or order.currency != CURRENCY:
            raise PaymentRejected("The donation amount does not match the paid order.")
        payment = gateway.fetch_payment(payment_id)
        if (payment.get("id") != payment_id or payment.get("order_id") != order_id
                or payment.get("amount") != order.amount_paise or payment.get("currency") != order.currency
                or payment.get("status") != "captured"):
            raise PaymentRejected("Razorpay does not report a captured payment for this order and amount.")
        return PaymentService._claim_and_record(db, campaign, order, payment_id, donation_in, donor_id, signature)

    @staticmethod
    def handle_webhook(db: Session, body: bytes, signature_header: Optional[str]) -> Dict[str, str]:
        """Server-to-server confirmation (e.g. the donor closed the tab after paying).  Fails closed."""
        secret = webhook_secret()
        if not secret:
            raise PaymentUnavailable("Razorpay webhooks are not configured on this server.")
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if not signature_header or not hmac.compare_digest(expected, signature_header.strip()):
            raise PaymentRejected("Invalid webhook signature.")
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise PaymentRejected("Malformed webhook body.") from exc
        if data.get("event") not in ("payment.captured", "order.paid"):
            return {"status": "ignored"}
        entity = (((data.get("payload") or {}).get("payment") or {}).get("entity") or {})
        order_id, payment_id = str(entity.get("order_id") or ""), str(entity.get("id") or "")
        if not (ORDER_ID.fullmatch(order_id) and PAYMENT_ID.fullmatch(payment_id)):
            raise PaymentRejected("Webhook payment details are malformed.")
        order = db.query(PaymentOrder).filter(PaymentOrder.gateway_order_id == order_id).first()
        if order is None:
            return {"status": "ignored"}                                # not an order created by this server
        if entity.get("amount") != order.amount_paise or entity.get("currency") != order.currency \
                or entity.get("status") != "captured":
            raise PaymentRejected("Webhook payment does not match the stored order.")
        campaign = db.query(Campaign).filter(Campaign.id == order.campaign_id).first()
        notes = entity.get("notes") or {}
        donation_in = DonationCreate(amount=order.amount_paise / 100.0, payment_method="RAZORPAY",
                                     donor_name=notes.get("donor_name") or "Kind Supporter",
                                     donor_email=entity.get("email"), donor_phone=entity.get("contact"),
                                     gateway_order_id=order_id, gateway_payment_id=payment_id)
        try:
            PaymentService._claim_and_record(db, campaign, order, payment_id, donation_in, None, None)
        except PaymentAlreadyRecorded:
            return {"status": "duplicate"}
        return {"status": "recorded"}


payment_service = PaymentService()
