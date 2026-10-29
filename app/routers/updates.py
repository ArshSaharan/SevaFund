from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.campaign import Campaign
from app.models.update import CampaignUpdate
from app.models.user import User
from app.schemas.update import UpdateCreate, UpdateResponse
from app.routers.auth import get_current_user

router = APIRouter(tags=["Campaign Updates"])

@router.post("/campaigns/{campaign_id}/updates", response_model=UpdateResponse, status_code=status.HTTP_201_CREATED)
def post_campaign_update(
    campaign_id: int,
    update_in: UpdateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.creator_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the campaign organizer can post updates")

    update_obj = CampaignUpdate(
        campaign_id=campaign.id,
        title=update_in.title,
        content=update_in.content,
        image_url=update_in.image_url,
        receipt_evidence_url=update_in.receipt_evidence_url
    )
    db.add(update_obj)
    db.commit()
    db.refresh(update_obj)

    return update_obj

@router.get("/campaigns/{campaign_id}/updates", response_model=List[UpdateResponse])
def list_campaign_updates(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    updates = (
        db.query(CampaignUpdate)
        .filter(CampaignUpdate.campaign_id == campaign_id)
        .order_by(desc(CampaignUpdate.created_at))
        .all()
    )
    return updates
