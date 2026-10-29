import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.campaign import Campaign
from app.models.payout import PayoutRequest
from app.models.user import User
from app.schemas.payout import PayoutCreate, PayoutResponse
from app.routers.auth import get_current_user

router = APIRouter(tags=["Payouts & Indian Bank Settlements"])

@router.post("/campaigns/{campaign_id}/payouts", response_model=PayoutResponse, status_code=status.HTTP_201_CREATED)
def request_payout(
    campaign_id: int,
    payout_in: PayoutCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.creator_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the campaign creator can request payouts")

    if campaign.status in ("FLAGGED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payouts are temporarily frozen because campaign is in '{campaign.status}' state."
        )

    # Calculate already paid or pending withdrawals
    existing_payouts = (
        db.query(PayoutRequest)
        .filter(PayoutRequest.campaign_id == campaign_id, PayoutRequest.status.in_(["PENDING_REVIEW", "APPROVED", "PAID"]))
        .all()
    )
    total_withdrawn = sum(p.amount for p in existing_payouts)
    available_balance = round(campaign.current_amount - total_withdrawn, 2)

    if payout_in.amount > available_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested withdrawal (₹{payout_in.amount:,.2f}) exceeds available balance (₹{available_balance:,.2f})."
        )

    # Validate 11-char IFSC format
    ifsc = payout_in.ifsc_code.strip().upper()
    if len(ifsc) != 11:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid IFSC Code. Indian IFSC code must be exactly 11 characters (e.g. SBIN0001234)."
        )

    payout = PayoutRequest(
        campaign_id=campaign.id,
        amount=round(payout_in.amount, 2),
        currency="INR",
        payout_method=payout_in.payout_method or "NEFT_IMPS_RTGS",
        bank_name=payout_in.bank_name,
        ifsc_code=ifsc,
        account_number_last4=payout_in.account_number[-4:],
        upi_id=payout_in.upi_id,
        beneficiary_pan=payout_in.beneficiary_pan.upper() if payout_in.beneficiary_pan else None,
        status="PENDING_REVIEW"
    )

    db.add(payout)
    db.commit()
    db.refresh(payout)

    return payout

@router.get("/campaigns/{campaign_id}/payouts", response_model=List[PayoutResponse])
def list_campaign_payouts(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.creator_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view payouts")

    payouts = (
        db.query(PayoutRequest)
        .filter(PayoutRequest.campaign_id == campaign_id)
        .order_by(desc(PayoutRequest.created_at))
        .all()
    )
    return payouts
