import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.database import get_db
from app.services import dev_hybrid_v4_flag  # development-only hybrid v4 integration; OFF unless SEVAFUND_DEV_HYBRID_V4=1
from app.models.campaign import Campaign
from app.models.donation import Donation
from app.schemas.donation import (
    DonationCreate,
    DonationResponse,
    DonationReceipt,
    CreateGatewayOrderRequest,
    CreateGatewayOrderResponse
)
from app.services.payment_service import (payment_service, PaymentAlreadyRecorded, PaymentRejected,
                                          PaymentUnavailable)
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
    if dev_hybrid_v4_flag.enabled():  # development-only: money moves only after all four independent confirmations
        from app.services import dev_hybrid_v4_integration
        blocked = dev_hybrid_v4_integration.funds_block_reason(db, campaign)
        if blocked:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=blocked)

    if (req.currency or "INR").upper() != "INR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only INR payments are supported.")
    try:
        order_info = payment_service.create_gateway_order(db, campaign, req.amount, req.tip_amount)
    except PaymentUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
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
    if dev_hybrid_v4_flag.enabled():  # development-only: money moves only after all four independent confirmations
        from app.services import dev_hybrid_v4_integration
        blocked = dev_hybrid_v4_integration.funds_block_reason(db, campaign)
        if blocked:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=blocked)

    # A donation is recorded only for a verified, captured Razorpay payment of a stored order of this campaign.
    donor_id = current_user.id if current_user else None
    try:
        donation = payment_service.record_verified_donation(db=db, campaign=campaign, donation_in=donation_in,
                                                            donor_id=donor_id)
    except PaymentRejected as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PaymentAlreadyRecorded as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PaymentUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

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
    Razorpay server-to-server callback.  Requires RAZORPAY_WEBHOOK_SECRET and a valid X-Razorpay-Signature over the
    raw body; the payment must match a stored order (amount, currency, captured).  Each payment is recorded once.
    """
    body_bytes = await request.body()
    try:
        return payment_service.handle_webhook(db, body_bytes, request.headers.get("X-Razorpay-Signature"))
    except PaymentRejected as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PaymentUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
