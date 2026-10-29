import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func

from app.database import get_db
from app.models.campaign import Campaign
from app.models.donation import Donation
from app.models.verification import VerificationAudit
from app.models.audit_log import AdminAuditLog
from app.models.user import User
from app.schemas.campaign import CampaignResponse, AdminDecisionRequest
from app.schemas.donation import AdminDonationsResponse, AdminDonationItem, AdminDonationsSummary
from app.routers.campaigns import format_campaign_response
from app.services.auth_dependencies import require_admin, require_trust_reviewer_or_admin

router = APIRouter(prefix="/admin", tags=["Trust & Safety Admin"])

@router.get("/flagged", response_model=List[CampaignResponse])
def get_flagged_campaigns(
    min_risk: Optional[str] = Query(None, description="Filter by risk: CRITICAL, HIGH, MEDIUM"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    STRICT ADMIN ONLY: Retrieves the queue of campaigns requiring human trust & safety moderation.
    Includes campaigns flagged by AI or awaiting administrative approval.
    """
    query = db.query(Campaign).filter(
        Campaign.status.in_(["FLAGGED", "PENDING_VERIFICATION", "REJECTED"])
    )

    if min_risk:
        query = query.filter(Campaign.risk_level == min_risk.upper())

    # Show lowest authenticity score / highest risk first
    campaigns = query.order_by(Campaign.authenticity_score.asc()).all()
    return [format_campaign_response(c) for c in campaigns]

@router.post("/campaigns/{campaign_id}/decision", response_model=CampaignResponse)
def submit_admin_decision(
    campaign_id: int,
    decision_in: AdminDecisionRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    STRICT ADMIN ONLY: Accepts or rejects a campaign demand.
    Only users with role == 'ADMIN' can execute this action.
    Decisions: APPROVE, REJECT, REQUEST_MORE_INFO.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    decision = decision_in.decision.upper().strip()
    previous_status = campaign.status

    if decision in ["APPROVE", "APPROVED"]:
        campaign.status = "ACTIVE"
    elif decision in ["REJECT", "REJECTED"]:
        campaign.status = "REJECTED"
    elif decision in ["REQUEST_MORE_INFO", "NEEDS_MORE_INFO"]:
        campaign.status = "PENDING_VERIFICATION"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be APPROVE, REJECT, or REQUEST_MORE_INFO"
        )

    # 1. Update latest verification audit with admin note
    latest_audit = (
        db.query(VerificationAudit)
        .filter(VerificationAudit.campaign_id == campaign_id)
        .order_by(desc(VerificationAudit.created_at))
        .first()
    )
    if latest_audit:
        latest_audit.admin_notes = f"Decision by {current_user.full_name} (Admin ID: {current_user.id}): {decision}. Notes: {decision_in.notes or 'None'}"
        latest_audit.reviewed_at = datetime.datetime.utcnow()

    # 2. Record immutable Admin Audit Log
    client_ip = request.client.host if request.client else None
    audit_log = AdminAuditLog(
        admin_id=current_user.id,
        action=f"CAMPAIGN_{campaign.status}",
        target_type="CAMPAIGN",
        target_id=campaign.id,
        previous_status=previous_status,
        new_status=campaign.status,
        reason=decision_in.notes or f"Admin decision: {decision}",
        ip_address=client_ip
    )
    db.add(audit_log)

    campaign.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(campaign)

    return format_campaign_response(campaign)

@router.get("/audit-logs")
def get_admin_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    STRICT ADMIN ONLY: Retrieves tamper-evident log of all admin accept/reject actions.
    """
    logs = (
        db.query(AdminAuditLog)
        .order_by(desc(AdminAuditLog.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id,
            "admin_id": l.admin_id,
            "action": l.action,
            "target_id": l.target_id,
            "previous_status": l.previous_status,
            "new_status": l.new_status,
            "reason": l.reason,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]

@router.get("/verifications")
def list_verification_audits(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    STRICT ADMIN ONLY: Retrieves recent AI audit trails.
    """
    audits = (
        db.query(VerificationAudit)
        .order_by(desc(VerificationAudit.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "campaign_id": a.campaign_id,
            "overall_score": a.overall_score,
            "risk_level": a.risk_level,
            "recommendation": a.recommendation,
            "plausibility_score": a.plausibility_score,
            "specificity_score": a.specificity_score,
            "red_flag_score": a.red_flag_score,
            "documentation_score": a.documentation_score,
            "admin_notes": a.admin_notes,
            "created_at": a.created_at
        }
        for a in audits
    ]

@router.get("/donations", response_model=AdminDonationsResponse)
def list_admin_donations(
    campaign_id: Optional[int] = Query(None, description="Filter donations by campaign ID"),
    search: Optional[str] = Query(None, description="Search by donor name, email, phone, PAN, tx ref, or beneficiary name"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    STRICT ADMIN ONLY: Retrieves complete ledger of all donations across the platform.
    Admin can check how much and who paid to each requested person (beneficiary).
    Includes full donor identity, PAN, payment method, fees, net amount, and transaction refs.
    """
    query = db.query(Donation).join(Campaign, Donation.campaign_id == Campaign.id)

    if campaign_id:
        query = query.filter(Donation.campaign_id == campaign_id)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Donation.donor_name.ilike(search_pattern),
                Donation.donor_email.ilike(search_pattern),
                Donation.donor_phone.ilike(search_pattern),
                Donation.donor_pan.ilike(search_pattern),
                Donation.transaction_ref.ilike(search_pattern),
                Donation.payment_method.ilike(search_pattern),
                Campaign.title.ilike(search_pattern),
                Campaign.beneficiary_name.ilike(search_pattern)
            )
        )

    total_count = query.count()

    # Aggregate totals for the query in a single clean query on the subquery
    subq = query.subquery()
    totals_row = db.query(
        func.coalesce(func.sum(subq.c.amount), 0.0),
        func.coalesce(func.sum(subq.c.net_amount), 0.0),
        func.coalesce(func.sum(subq.c.fee_amount), 0.0)
    ).first()

    sum_amount = float(totals_row[0]) if totals_row else 0.0
    sum_net = float(totals_row[1]) if totals_row else 0.0
    sum_fee = float(totals_row[2]) if totals_row else 0.0
    avg_donation = round(sum_amount / total_count, 2) if total_count > 0 else 0.0

    donations = (
        query.order_by(desc(Donation.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = []
    for d in donations:
        c = d.campaign
        items.append(
            AdminDonationItem(
                id=d.id,
                campaign_id=d.campaign_id,
                campaign_title=c.title if c else "Unknown Campaign",
                beneficiary_name=c.beneficiary_name if c else None,
                beneficiary_type=c.beneficiary_type if c else None,
                hospital_name=c.hospital_name if c else None,
                donor_id=d.donor_id,
                donor_name=d.donor_name,
                is_anonymous=d.is_anonymous,
                donor_email=d.donor_email,
                donor_phone=d.donor_phone,
                donor_pan=d.donor_pan,
                amount=d.amount,
                tip_amount=d.tip_amount,
                fee_amount=d.fee_amount,
                net_amount=d.net_amount,
                currency=d.currency or "INR",
                payment_method=d.payment_method or "UPI",
                upi_id=d.upi_id,
                tax_exemption_80g_number=d.tax_exemption_80g_number,
                support_message=d.support_message,
                payment_status=d.payment_status or "COMPLETED",
                transaction_ref=d.transaction_ref,
                gateway_order_id=d.gateway_order_id,
                gateway_payment_id=d.gateway_payment_id,
                created_at=d.created_at
            )
        )

    return AdminDonationsResponse(
        items=items,
        total=total_count,
        page=page,
        limit=limit,
        summary=AdminDonationsSummary(
            total_donations_count=total_count,
            total_amount_raised=round(sum_amount, 2),
            total_net_amount=round(sum_net, 2),
            total_fee_amount=round(sum_fee, 2),
            average_donation=avg_donation
        )
    )
