import os
import json
import hmac
import hashlib
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.database import get_db
from app.models.campaign import Campaign
from app.models.donation import Donation
from app.schemas.donation import (
    DonationCreate,
    DonationResponse,
    DonationReceipt,
    CreateGatewayOrderRequest,
    CreateGatewayOrderResponse
)
from app.services.payment_service import payment_service
from app.routers.auth import get_current_user_optional

router = APIRouter(tags=["Donations & Indian Payments"])

@router.post("/donations/create-order", response_model=CreateGatewayOrderResponse)
def create_payment_order(
    req: CreateGatewayOrderRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a payment gateway order (Razorpay standard) for a campaign.
    Converts amount to paise and returns order details for frontend Checkout.
    """
    campaign = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.status in ("REJECTED", "PAUSED", "COMPLETED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This campaign is currently {campaign.status.lower()} and cannot receive donations."
        )

    order_info = payment_service.create_gateway_order(campaign, req.amount)
    return CreateGatewayOrderResponse(
        order_id=order_info["order_id"],
        amount=order_info["amount"],
        currency=order_info["currency"],
        key_id=order_info["key_id"],
        campaign_id=campaign.id,
        campaign_title=campaign.title,
        beneficiary_name=campaign.beneficiary_name
    )

@router.post("/campaigns/{campaign_id}/donate", response_model=DonationReceipt, status_code=status.HTTP_201_CREATED)
def make_donation(
    campaign_id: int,
    donation_in: DonationCreate,
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.status in ("REJECTED", "PAUSED", "COMPLETED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This campaign is currently {campaign.status.lower()} and cannot receive donations."
        )

    # Optional signature verification if razorpay order was used
    if donation_in.gateway_order_id and donation_in.gateway_payment_id and donation_in.gateway_signature:
        is_valid = payment_service.verify_gateway_signature(
            donation_in.gateway_order_id,
            donation_in.gateway_payment_id,
            donation_in.gateway_signature
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed."
            )

    donor_id = current_user.id if current_user else None
    donation = payment_service.process_donation(
        db=db,
        campaign=campaign,
        donation_in=donation_in,
        donor_id=donor_id
    )

    total_charged = round(donation.amount + donation.tip_amount, 2)
    tax_note = f" 80G Tax Exemption Certificate #{donation.tax_exemption_80g_number} issued for Income Tax deduction." if donation.tax_exemption_80g_number else ""

    return DonationReceipt(
        transaction_ref=donation.transaction_ref,
        campaign_id=campaign.id,
        campaign_title=campaign.title,
        donor_name="Anonymous" if donation.is_anonymous else donation.donor_name,
        amount=donation.amount,
        tip_amount=donation.tip_amount,
        total_charged=total_charged,
        currency="INR",
        payment_method=donation.payment_method,
        tax_exemption_80g_number=donation.tax_exemption_80g_number,
        gateway_order_id=donation.gateway_order_id,
        gateway_payment_id=donation.gateway_payment_id,
        timestamp=donation.created_at,
        receipt_message=f"Dhanyavaad! Your donation has been securely received via {donation.payment_method} and credited to the campaign.{tax_note}"
    )

@router.get("/campaigns/{campaign_id}/donations", response_model=List[DonationResponse])
def list_campaign_donations(
    campaign_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    donations = (
        db.query(Donation)
        .filter(Donation.campaign_id == campaign_id, Donation.payment_status == "COMPLETED")
        .order_by(desc(Donation.created_at))
        .limit(limit)
        .all()
    )

    results = []
    for d in donations:
        display_name = "Anonymous Supporter" if d.is_anonymous else d.donor_name
        results.append(
            DonationResponse(
                id=d.id,
                campaign_id=d.campaign_id,
                donor_id=None if d.is_anonymous else d.donor_id,
                donor_name=display_name,
                amount=d.amount,
                tip_amount=d.tip_amount,
                fee_amount=d.fee_amount,
                net_amount=d.net_amount,
                currency="INR",
                payment_method=d.payment_method,
                upi_id=d.upi_id,
                tax_exemption_80g_number=d.tax_exemption_80g_number,
                support_message=d.support_message,
                is_anonymous=d.is_anonymous,
                payment_status=d.payment_status,
                transaction_ref=d.transaction_ref,
                created_at=d.created_at
            )
        )
    return results

@router.get("/donations/{transaction_ref}", response_model=DonationReceipt)
def get_donation_receipt(transaction_ref: str, db: Session = Depends(get_db)):
    donation = db.query(Donation).filter(Donation.transaction_ref == transaction_ref).first()
    if not donation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donation record not found")

    campaign = db.query(Campaign).filter(Campaign.id == donation.campaign_id).first()
    campaign_title = campaign.title if campaign else "Crowdfunding Campaign"

    return DonationReceipt(
        transaction_ref=donation.transaction_ref,
        campaign_id=donation.campaign_id,
        campaign_title=campaign_title,
        donor_name="Anonymous" if donation.is_anonymous else donation.donor_name,
        amount=donation.amount,
        tip_amount=donation.tip_amount,
        total_charged=round(donation.amount + donation.tip_amount, 2),
        currency="INR",
        payment_method=donation.payment_method,
        tax_exemption_80g_number=donation.tax_exemption_80g_number,
        timestamp=donation.created_at,
        receipt_message="Verified Indian Transaction Receipt (INR)"
    )

@router.post("/donations/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Production Webhook Endpoint for Razorpay Server-to-Server callbacks.
    Ensures donations are fulfilled even if the donor closes the browser tab after UPI payment.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET") or settings.RAZORPAY_KEY_SECRET
    if webhook_secret and webhook_secret != "mock_razorpay_secret" and signature:
        expected = hmac.new(webhook_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"status": "ignored"}

    event = data.get("event")
    if event in ("payment.captured", "order.paid"):
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")
        notes = payment_entity.get("notes", {})
        campaign_id = notes.get("campaign_id")

        if campaign_id:
            campaign = db.query(Campaign).filter(Campaign.id == int(campaign_id)).first()
            if campaign:
                existing = db.query(Donation).filter(
                    (Donation.gateway_payment_id == payment_id) | 
                    ((Donation.gateway_order_id == order_id) & (Donation.gateway_order_id.isnot(None)))
                ).first()
                if not existing:
                    amount_inr = payment_entity.get("amount", 0) / 100.0
                    donation_in = DonationCreate(
                        amount=amount_inr,
                        donor_name=notes.get("donor_name") or payment_entity.get("email") or "Kind Supporter",
                        donor_email=payment_entity.get("email"),
                        donor_phone=payment_entity.get("contact"),
                        payment_method="RAZORPAY",
                        gateway_order_id=order_id,
                        gateway_payment_id=payment_id
                    )
                    payment_service.process_donation(db, campaign, donation_in)

    return {"status": "ok"}
