"""Development-only endpoints for the hybrid v4 workflow (flag SEVAFUND_DEV_HYBRID_V4; 404 when the flag is off).

Hidden from the OpenAPI schema.  Confirmations are entered by an admin or trust reviewer who obtained them through
an independent channel; this router does not contact anyone and is not connected to any verification service.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.campaign import Campaign
from app.models.user import User
from app.services import dev_hybrid_v4_flag
from app.services.auth_dependencies import get_current_user, require_trust_reviewer_or_admin

router = APIRouter(prefix="/dev/hybrid-v4", tags=["Development: hybrid v4"], include_in_schema=False)


class ConfirmationIn(BaseModel):
    check: Literal["BENEFICIARY", "INSTITUTION", "PAYMENT_DESTINATION", "AMOUNT"]
    outcome: Literal["CONFIRMED", "CONTRADICTED", "UNREACHABLE", "INCONCLUSIVE"]
    contact_source: Literal["OFFICIAL_REGISTRY", "OFFICIAL_DIRECTORY", "PLATFORM_KYC", "PRIOR_VERIFIED_RECORD",
                            "CAMPAIGN_SUPPLIED"]
    contact_reference: str = ""
    stated_amount_inr: Optional[float] = Field(None, ge=0, description="AMOUNT only: what the cost issuer states is due")
    other_payers_inr: float = Field(0, ge=0, description="AMOUNT only: already covered by insurance, scheme, scholarship")
    note: str = ""


class AssistedReviewIn(BaseModel):
    reason: str = "Applicant has no formal quotation; the amount will be obtained from the cost issuer."


def _campaign(db: Session, campaign_id: int) -> Campaign:
    if not dev_hybrid_v4_flag.enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


def _integration():
    from app.services import dev_hybrid_v4_integration
    return dev_hybrid_v4_integration


@router.get("/campaigns/{campaign_id}")
def get_record(campaign_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_id)
    staff = current_user.role in ("ADMIN", "TRUST_REVIEWER")
    if campaign.creator_id != current_user.id and not staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
    return _integration().summary(db, campaign, include_audit=staff)


@router.post("/campaigns/{campaign_id}/confirmations")
def post_confirmation(campaign_id: int, body: ConfirmationIn,
                      current_user: User = Depends(require_trust_reviewer_or_admin), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_id)
    integration = _integration()
    integration.add_confirmation(db, campaign, body, current_user)
    db.commit()
    db.refresh(campaign)
    return integration.summary(db, campaign)


@router.post("/campaigns/{campaign_id}/assisted-cost-review")
def post_assisted_review(campaign_id: int, body: AssistedReviewIn,
                         current_user: User = Depends(require_trust_reviewer_or_admin), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_id)
    integration = _integration()
    integration.start_assisted_review(db, campaign, current_user, body.reason)
    db.commit()
    db.refresh(campaign)
    return integration.summary(db, campaign)
