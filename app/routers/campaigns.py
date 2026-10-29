import json
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.database import get_db
from app.models.user import User
from app.models.campaign import Campaign
from app.models.verification import VerificationAudit
from app.schemas.campaign import CampaignCreate, CampaignUpdateSchema, CampaignResponse, CampaignListResponse
from app.schemas.ai import VerificationResult
from app.services.ai_verifier import ai_verifier
from app.services.auth_dependencies import get_current_user, get_current_user_or_demo

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

def format_campaign_response(campaign: Campaign) -> dict:
    percent = round((campaign.current_amount / campaign.goal_amount * 100), 1) if campaign.goal_amount > 0 else 0.0
    docs = []
    if campaign.proof_documents_json:
        try:
            docs = json.loads(campaign.proof_documents_json)
        except Exception:
            docs = []

    return {
        "id": campaign.id,
        "creator_id": campaign.creator_id,
        "title": campaign.title,
        "subtitle": campaign.subtitle,
        "category": campaign.category,
        "story": campaign.story,
        "goal_amount": campaign.goal_amount,
        "current_amount": campaign.current_amount,
        "currency": campaign.currency,
        "donor_count": campaign.donor_count,
        "percent_funded": percent,
        "cover_image_url": campaign.cover_image_url,
        "country": campaign.country or "IN",
        "state": campaign.state,
        "city": campaign.city,
        "postal_code": campaign.postal_code,
        "beneficiary_type": campaign.beneficiary_type,
        "beneficiary_name": campaign.beneficiary_name,
        "relationship_to_beneficiary": campaign.relationship_to_beneficiary,
        "hospital_name": campaign.hospital_name,
        "hospital_patient_uhid": campaign.hospital_patient_uhid,
        "is_80g_tax_exempt": campaign.is_80g_tax_exempt,
        "direct_hospital_transfer": campaign.direct_hospital_transfer,
        "status": campaign.status,
        "proof_documents": docs,
        "authenticity_score": campaign.authenticity_score,
        "risk_level": campaign.risk_level,
        "ai_recommendation": campaign.ai_recommendation,
        "ai_verified_at": campaign.ai_verified_at,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
        "deadline": campaign.deadline
    }

@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    category: Optional[str] = Query(None, description="Filter by category (MEDICAL, EMERGENCY, etc.)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (ACTIVE, etc.)"),
    search: Optional[str] = Query(None, description="Search keyword in title or story"),
    min_score: Optional[float] = Query(None, description="Minimum authenticity score filter"),
    sort_by: str = Query("trending", description="Sort by: trending, newest, most_funded"),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Campaign)

    # By default, public listing only returns ACTIVE campaigns unless an explicit status is given
    if status_filter:
        query = query.filter(Campaign.status == status_filter.upper())
    else:
        query = query.filter(Campaign.status.in_(["ACTIVE", "PENDING_VERIFICATION"]))

    if category:
        query = query.filter(Campaign.category.ilike(f"%{category}%"))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Campaign.title.ilike(search_pattern),
                Campaign.story.ilike(search_pattern),
                Campaign.city.ilike(search_pattern),
                Campaign.beneficiary_name.ilike(search_pattern)
            )
        )

    if min_score is not None:
        query = query.filter(Campaign.authenticity_score >= min_score)

    if sort_by == "newest":
        query = query.order_by(desc(Campaign.created_at))
    elif sort_by == "most_funded":
        query = query.order_by(desc(Campaign.current_amount))
    else:  # trending default (donor count & raised amount)
        query = query.order_by(desc(Campaign.donor_count), desc(Campaign.current_amount))

    total = query.count()
    campaigns = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [format_campaign_response(c) for c in campaigns],
        "total": total,
        "page": page,
        "limit": limit
    }

@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_in: CampaignCreate,
    current_user: User = Depends(get_current_user_or_demo),
    db: Session = Depends(get_db)
):
    # Convert proof documents to JSON
    docs_json = json.dumps([d.model_dump() for d in campaign_in.proof_documents]) if campaign_in.proof_documents else None

    # Step 1: Run AI Verification pipeline immediately on campaign submission
    docs_data = [d.model_dump() for d in campaign_in.proof_documents] if campaign_in.proof_documents else []
    location_str = f"{campaign_in.city or ''}, {campaign_in.state or ''} {campaign_in.country or 'US'}".strip(", ")
    
    ai_result: VerificationResult = await ai_verifier.verify_campaign_request(
        title=campaign_in.title,
        category=campaign_in.category,
        story=campaign_in.story,
        goal_amount=campaign_in.goal_amount,
        beneficiary_name=campaign_in.beneficiary_name,
        beneficiary_type=campaign_in.beneficiary_type,
        location=location_str,
        proof_documents=docs_data
    )

    # Industry requirement: Only an admin can accept (activate) or reject a fundraiser demand.
    # The AI computes the authenticity score, cost checks, and red flags for the admin queue.
    if ai_result.recommendation in ["FLAG_FOR_REVIEW", "REJECT"] or (ai_result.red_flags and len(ai_result.red_flags) > 0):
        initial_status = "FLAGGED"
    else:
        initial_status = "PENDING_VERIFICATION"

    campaign = Campaign(
        creator_id=current_user.id,
        title=campaign_in.title,
        subtitle=campaign_in.subtitle,
        category=campaign_in.category.upper(),
        story=campaign_in.story,
        goal_amount=round(campaign_in.goal_amount, 2),
        current_amount=0.0,
        currency="INR",
        donor_count=0,
        cover_image_url=campaign_in.cover_image_url,
        country=campaign_in.country or "IN",
        state=campaign_in.state,
        city=campaign_in.city,
        postal_code=campaign_in.postal_code,
        beneficiary_type=campaign_in.beneficiary_type,
        beneficiary_name=campaign_in.beneficiary_name,
        relationship_to_beneficiary=campaign_in.relationship_to_beneficiary,
        hospital_name=campaign_in.hospital_name,
        hospital_patient_uhid=campaign_in.hospital_patient_uhid,
        is_80g_tax_exempt=campaign_in.is_80g_tax_exempt,
        direct_hospital_transfer=campaign_in.direct_hospital_transfer,
        status=initial_status,
        proof_documents_json=docs_json,
        authenticity_score=ai_result.authenticity_score,
        risk_level=ai_result.risk_level,
        ai_recommendation=ai_result.recommendation,
        ai_verified_at=datetime.datetime.utcnow(),
        deadline=campaign_in.deadline
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Save detailed AI Verification Audit record
    audit = VerificationAudit(
        campaign_id=campaign.id,
        overall_score=ai_result.authenticity_score,
        risk_level=ai_result.risk_level,
        recommendation=ai_result.recommendation,
        plausibility_score=ai_result.dimension_scores.plausibility,
        specificity_score=ai_result.dimension_scores.specificity,
        red_flag_score=ai_result.dimension_scores.red_flag_score,
        documentation_score=ai_result.dimension_scores.documentation,
        summary=ai_result.summary,
        detailed_analysis_json=json.dumps(ai_result.model_dump()),
        model_name=ai_result.model_used
    )
    db.add(audit)
    db.commit()

    return format_campaign_response(campaign)

@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return format_campaign_response(campaign)

@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    update_in: CampaignUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    
    if campaign.creator_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this campaign")

    update_dict = update_in.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        setattr(campaign, field, val)

    campaign.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return format_campaign_response(campaign)

@router.post("/{campaign_id}/verify", response_model=VerificationResult)
async def verify_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Triggers or re-evaluates the AI Verification engine on an existing campaign.
    Updates the campaign's authenticity score and logs a new audit trail.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    docs = []
    if campaign.proof_documents_json:
        try:
            docs = json.loads(campaign.proof_documents_json)
        except Exception:
            docs = []

    location_str = f"{campaign.city or ''}, {campaign.state or ''} {campaign.country or 'US'}".strip(", ")

    ai_result: VerificationResult = await ai_verifier.verify_campaign_request(
        title=campaign.title,
        category=campaign.category,
        story=campaign.story,
        goal_amount=campaign.goal_amount,
        beneficiary_name=campaign.beneficiary_name,
        beneficiary_type=campaign.beneficiary_type,
        location=location_str,
        proof_documents=docs
    )

    campaign.authenticity_score = ai_result.authenticity_score
    campaign.risk_level = ai_result.risk_level
    campaign.ai_recommendation = ai_result.recommendation
    campaign.ai_verified_at = datetime.datetime.utcnow()

    if ai_result.recommendation == "AUTO_APPROVE" and campaign.status in ("PENDING_VERIFICATION", "FLAGGED"):
        campaign.status = "ACTIVE"
    elif ai_result.recommendation == "REJECT":
        campaign.status = "REJECTED"

    audit = VerificationAudit(
        campaign_id=campaign.id,
        overall_score=ai_result.authenticity_score,
        risk_level=ai_result.risk_level,
        recommendation=ai_result.recommendation,
        plausibility_score=ai_result.dimension_scores.plausibility,
        specificity_score=ai_result.dimension_scores.specificity,
        red_flag_score=ai_result.dimension_scores.red_flag_score,
        documentation_score=ai_result.dimension_scores.documentation,
        summary=ai_result.summary,
        detailed_analysis_json=json.dumps(ai_result.model_dump()),
        model_name=ai_result.model_used
    )
    db.add(audit)
    db.commit()
    db.refresh(campaign)

    return ai_result

@router.get("/{campaign_id}/audit")
def get_campaign_latest_audit(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    latest_audit = (
        db.query(VerificationAudit)
        .filter(VerificationAudit.campaign_id == campaign_id)
        .order_by(desc(VerificationAudit.created_at))
        .first()
    )

    if not latest_audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No verification audit found for this campaign")

    analysis_data = {}
    try:
        analysis_data = json.loads(latest_audit.detailed_analysis_json)
    except Exception:
        pass

    return {
        "audit_id": latest_audit.id,
        "campaign_id": campaign_id,
        "overall_score": latest_audit.overall_score,
        "risk_level": latest_audit.risk_level,
        "recommendation": latest_audit.recommendation,
        "dimensions": {
            "plausibility": latest_audit.plausibility_score,
            "specificity": latest_audit.specificity_score,
            "red_flag_score": latest_audit.red_flag_score,
            "documentation": latest_audit.documentation_score
        },
        "summary": latest_audit.summary,
        "detailed_analysis": analysis_data,
        "created_at": latest_audit.created_at
    }
