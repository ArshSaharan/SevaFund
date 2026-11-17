"""Development-only integration of hybrid v4 into the SevaFund application (flag SEVAFUND_DEV_HYBRID_V4, OFF by default).

Loaded only when the flag is on (see dev_hybrid_v4_flag.py).  With the flag on:

  * Campaign creation and re-verification run hybrid v4 (frozen V3 + frozen hybrid v3 + v4 additions) on the
    campaign's text and its uploaded documents, and start a persisted hybrid v4 workflow record.  The production
    score is still computed and stored, but it never decides the campaign's status.
  * Campaign status follows the hybrid v4 workflow state.  ACTIVE is reached ONLY through recorded confirmations of
    all four checks - beneficiary, institution, payment destination and requested amount - each through an
    independent source.  Neither the score, nor an admin decision, nor a reviewer can make a campaign ACTIVE.
  * Donations and payouts require an ACTIVE hybrid v4 record that passes its own re-check (four independent
    confirmations, amount within tolerance, intact audit chain); payouts are capped at the confirmed amount.
  * A goal change is refused once a campaign is pending confirmation, under review or active.

Gemini: the integration never calls the Gemini API.  It uses an offline scripted stand-in (SEVAFUND_DEV_HYBRID_V4_GEMINI)
whose answer is passed through the frozen hybrid-v2 client parser.  With the default mode 'off' Gemini is not run, and
hybrid v4 never approves.  Grounding is checked against the full text of the uploaded documents.
"""
import datetime
import json
from datetime import date
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.dev_hybrid_v4 import DevHybridV4Record
from app.services import rag
from app.services.dev_hybrid_v4_flag import enabled, gemini_mode
from app.services.development_approval_workflow.schemas import ConfirmationOutcome, ContactSource, WorkflowState
from app.services.development_gemini_verification import verify_with_gemini
from app.services.development_hybrid_v4 import (POLICY_VERSION, Check, Confirmation, IllegalTransition, Record,
                                                activation_status, assess_case, assisted_cost_review,
                                                record_confirmation, reviewer_resolution, start, suspend)
from app.services.gemini_api import GeminiAPIError

S = WorkflowState
STATUS_FOR_STATE = {
    S.VERIFIED_ACTIVE: "ACTIVE",
    S.ELIGIBLE_PENDING_CONFIRMATION: "PENDING_VERIFICATION",
    S.NEEDS_MORE_INFORMATION: "PENDING_VERIFICATION",
    S.VERIFICATION_ERROR: "PENDING_VERIFICATION",
    S.FLAG_FOR_REVIEW: "FLAGGED",
    S.REJECTED: "REJECTED",
}
KEEP_ON_REVERIFY = {S.ELIGIBLE_PENDING_CONFIRMATION, S.VERIFIED_ACTIVE, S.FLAG_FOR_REVIEW, S.REJECTED}
NOT_ACTIVE = ("Hybrid v4 (development): funds cannot be raised or released until the beneficiary, institution, payment "
              "destination and requested amount are each confirmed through an independent source.")


# ------------------------------------------------------------------ persistence
def _ensure_table(db: Session) -> None:
    DevHybridV4Record.__table__.create(bind=db.get_bind(), checkfirst=True)


def _row(db: Session, campaign_id: int) -> Optional[DevHybridV4Record]:
    _ensure_table(db)
    return db.query(DevHybridV4Record).filter(DevHybridV4Record.campaign_id == campaign_id).first()


def load(db: Session, campaign_id: int) -> Optional[Record]:
    row = _row(db, campaign_id)
    return Record.model_validate_json(row.record_json) if row else None


def _save(db: Session, campaign: Campaign, record: Record, decision_json: Optional[str] = None) -> None:
    row = _row(db, campaign.id)
    if row is None:
        row = DevHybridV4Record(campaign_id=campaign.id, previous_records_json="[]")
        db.add(row)
    elif decision_json is not None and row.record_json:               # re-verification replaces the record
        previous = json.loads(row.previous_records_json or "[]")
        previous.append(json.loads(row.record_json))
        row.previous_records_json = json.dumps(previous)
    row.state, row.decision, row.policy_version = record.state.value, record.decision, record.policy_version
    row.record_json = record.model_dump_json()
    if decision_json is not None:
        row.decision_json = decision_json
    campaign.status = STATUS_FOR_STATE[record.state]
    campaign.updated_at = datetime.datetime.utcnow()


# ------------------------------------------------------------------ case building
def _documents(campaign: Campaign) -> List[dict]:
    try:
        docs = json.loads(campaign.proof_documents_json or "[]")
    except ValueError:
        docs = []
    out = []
    upload_dir = rag.UPLOAD_DIR.resolve()
    for doc in docs:
        url, text = str(doc.get("file_url") or ""), ""
        if url.startswith("/private-documents/"):
            path = (upload_dir / url.rsplit("/", 1)[-1]).resolve()
            if path.parent == upload_dir and path.is_file():
                try:
                    text = rag.extract_document_text(path)        # local extraction only; never OCR or a URL fetch
                except (ValueError, RuntimeError, OSError):
                    text = ""
        out.append({"title": doc.get("title") or "Document", "doc_type": doc.get("doc_type") or "OTHER", "content": text})
    return out


def campaign_case(campaign: Campaign, reference: date) -> dict:
    btype = (campaign.beneficiary_type or "SELF").upper()
    return {"title": campaign.title, "category": (campaign.category or "OTHER").upper(), "story": campaign.story,
            "goal_amount": float(campaign.goal_amount), "goal_currency": "INR",
            "beneficiary_name": campaign.beneficiary_name,
            "beneficiary_type": "ORGANISATION" if btype in {"NGO_TRUST", "NGO", "ORGANIZATION"} else btype,
            "city": campaign.city, "state": campaign.state, "submitted_on": reference.isoformat(),
            "documents": _documents(campaign)}


def _campaign_text(case: dict) -> str:
    return " ".join([str(case.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state")] +
                    [d["content"] for d in case["documents"]])


# ------------------------------------------------------------------ offline Gemini stand-in (never calls the API)
def _body(recommendation: str, concerns: list, missing: list) -> dict:
    return {"authenticity_score": 72 if recommendation == "AUTO_APPROVE" else 45,
            "risk_level": "LOW" if recommendation == "AUTO_APPROVE" else "MEDIUM", "recommendation": recommendation,
            "summary": "Offline development stand-in; not a model output.",
            "dimension_scores": {"plausibility": 70, "specificity": 70, "red_flag_score": 70, "documentation": 70},
            "red_flags": [], "positive_signals": [], "missing_requirements": missing, "concerns": concerns}


def _scripted_transport(mode: str):
    async def transport(url, api_key, payload, stage, timeout, max_attempts=1):
        if mode == "mock-fail":
            raise GeminiAPIError(stage, "SERVER_ERROR", 503)
        body = {"mock-approve": _body("AUTO_APPROVE", [], []),
                "mock-nmi": _body("NEEDS_MORE_INFO", [{"category": "MISSING_INFORMATION",
                                                       "description": "A cost estimate or quotation is required."}],
                                  ["A cost estimate or quotation is required."]),
                "mock-flag-unquoted": _body("FLAG_FOR_REVIEW", [{"category": "SUSPECTED_FRAUD",
                                                                 "description": "The campaign may be fabricated."}], [])}[mode]
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(body)}]}}],
                "modelVersion": "dev-offline-mock", "usageMetadata": {}}
    return transport


async def gemini_outcome(case: dict, chunks: List[dict], reference: date) -> Optional[dict]:
    mode = gemini_mode()
    if mode == "off":
        return None
    outcome = await verify_with_gemini(case, chunks, reference, submitted_on=reference,
                                       transport=_scripted_transport(mode), api_key="dev-offline-mock-not-a-key",
                                       model="gemini-3.6-flash", max_attempts=1)
    return outcome.model_dump()


# ------------------------------------------------------------------ automated verification
async def assess_and_record(db: Session, campaign: Campaign) -> Record:
    """Run hybrid v4 for a new campaign, or re-run it after an information request or a verification error.  A record
    that is pending confirmation, under review, active or rejected is kept, so confirmations are never discarded."""
    existing = load(db, campaign.id)
    if existing is not None and existing.state in KEEP_ON_REVERIFY:
        _save(db, campaign, existing)
        return existing
    reference = (campaign.created_at or datetime.datetime.utcnow()).date()
    case = campaign_case(campaign, reference)
    chunks = [{"title": d["title"], "text": d["content"]} for d in case["documents"] if d["content"].strip()]
    decision = assess_case(case, await gemini_outcome(case, chunks, reference), chunks, reference)
    record = start(decision.decision, case, decision.information_requests, decision.manual_route,
                   decision.audit_payload(), case_id=f"campaign-{campaign.id}")
    _save(db, campaign, record, decision.model_dump_json())
    return record


# ------------------------------------------------------------------ confirmations and reviews
def _record_or_404(db: Session, campaign: Campaign) -> Record:
    record = load(db, campaign.id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This campaign has no hybrid v4 record; run verification first.")
    return record


def add_confirmation(db: Session, campaign: Campaign, body, verifier) -> Record:
    if verifier.id == campaign.creator_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The campaign creator cannot record its own confirmations.")
    record = _record_or_404(db, campaign)
    case = campaign_case(campaign, (campaign.created_at or datetime.datetime.utcnow()).date())
    confirmation = Confirmation(check=Check(body.check), outcome=ConfirmationOutcome(body.outcome),
                                contact_source=ContactSource(body.contact_source),
                                contact_reference=body.contact_reference or "", verifier_id=f"user-{verifier.id}",
                                note=body.note or "", stated_amount_inr=body.stated_amount_inr,
                                other_payers_inr=body.other_payers_inr or 0)
    try:
        record_confirmation(record, confirmation, _campaign_text(case))
    except IllegalTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    _save(db, campaign, record)
    return record


def start_assisted_review(db: Session, campaign: Campaign, caseworker, reason: str) -> Record:
    if caseworker.id == campaign.creator_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The campaign creator cannot act as caseworker.")
    record = _record_or_404(db, campaign)
    try:
        assisted_cost_review(record, f"user-{caseworker.id}", reason or "Assisted cost confirmation.")
    except IllegalTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    _save(db, campaign, record)
    return record


def admin_decision(db: Session, campaign: Campaign, decision: str, admin, notes: Optional[str]) -> bool:
    """Called by the admin decision endpoint when the flag is on.  True = handled here (status set from the hybrid v4
    record); False = no hybrid v4 record and the decision cannot activate anything, so the production path applies."""
    record = load(db, campaign.id)
    actor, reason = f"user-{admin.id}", notes or f"Admin decision: {decision}"
    approve, reject = decision in ("APPROVE", "APPROVED"), decision in ("REJECT", "REJECTED")
    more_info = decision in ("REQUEST_MORE_INFO", "NEEDS_MORE_INFO")
    if record is None:
        if approve:
            raise HTTPException(status.HTTP_409_CONFLICT, "Hybrid v4 (development): an admin cannot activate a campaign. "
                                "Run verification, then record the four independent confirmations.")
        return False
    try:
        if approve:
            if record.state != S.FLAG_FOR_REVIEW:
                raise HTTPException(status.HTTP_409_CONFLICT, "Hybrid v4 (development): approval cannot activate a "
                                    "campaign. Activation happens only when all four independent confirmations are "
                                    f"recorded (current state {record.state.value}).")
            reviewer_resolution(record, S.ELIGIBLE_PENDING_CONFIRMATION, actor, reason)   # cleared, NOT activated
        elif reject:
            if record.state == S.REJECTED:
                return True
            if record.state == S.VERIFICATION_ERROR:
                raise HTTPException(status.HTTP_409_CONFLICT, "Re-run verification before deciding.")
            if record.state != S.FLAG_FOR_REVIEW:
                suspend(record, actor, reason)
            reviewer_resolution(record, S.REJECTED, actor, reason)
        elif more_info:
            if record.state != S.FLAG_FOR_REVIEW:
                raise HTTPException(status.HTTP_409_CONFLICT, "Information can be requested only for a flagged campaign.")
            reviewer_resolution(record, S.NEEDS_MORE_INFORMATION, actor, reason)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Decision must be APPROVE, REJECT, or REQUEST_MORE_INFO")
    except IllegalTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    _save(db, campaign, record)
    return True


# ------------------------------------------------------------------ money guards
def funds_block_reason(db: Session, campaign: Campaign) -> Optional[str]:
    record = load(db, campaign.id)
    if record is None or record.state != S.VERIFIED_ACTIVE:
        return NOT_ACTIVE
    if not activation_status(record)["activation_valid"]:
        return "Hybrid v4 (development): the activation record failed its re-check; funds are frozen."
    return None


def payout_block_reason(db: Session, campaign: Campaign, already_requested: float, amount: float) -> Optional[str]:
    reason = funds_block_reason(db, campaign)
    if reason:
        return reason
    limit = load(db, campaign.id).disbursement_limit_inr or 0
    if already_requested + amount > limit + 0.005:
        return (f"Hybrid v4 (development): payouts are limited to the independently confirmed amount of "
                f"Rs {limit:,.2f}; Rs {already_requested:,.2f} is already requested.")
    return None


def goal_change_block_reason(db: Session, campaign: Campaign, new_goal) -> Optional[str]:
    if new_goal is None or float(new_goal) == float(campaign.goal_amount):
        return None
    record = load(db, campaign.id)
    if record is not None and record.state in KEEP_ON_REVERIFY:
        return ("Hybrid v4 (development): the goal cannot change once a campaign is pending confirmation, under review, "
                "active or rejected; the amount is confirmed against the goal.")
    return None


# ------------------------------------------------------------------ read model
def summary(db: Session, campaign: Campaign, include_audit: bool = False) -> dict:
    row = _row(db, campaign.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This campaign has no hybrid v4 record; run verification first.")
    record = Record.model_validate_json(row.record_json)
    decision = json.loads(row.decision_json)
    out = {"campaign_id": campaign.id, "campaign_status": campaign.status, "policy_version": POLICY_VERSION,
           "workflow_state": record.state.value, "automated_decision": record.decision,
           "explanation": decision.get("explanation"), "review_basis": decision.get("review_basis"),
           "findings": decision.get("findings"), "information_requests": record.information_requests,
           "manual_route": record.manual_route,
           "required_checks": [r.check.value for r in record.requirements],
           "confirmations": [{"check": c.check.value, "outcome": c.outcome.value, "contact_source": c.contact_source.value,
                              "stated_amount_inr": c.stated_amount_inr, "other_payers_inr": c.other_payers_inr}
                             for c in record.confirmations],
           "activation": activation_status(record),
           "previous_records": len(json.loads(row.previous_records_json or "[]")),
           "note": "Development integration. Gemini is an offline stand-in; confirmations are entered by staff and "
                   "are not connected to any real verification service."}
    if include_audit:
        out["audit_log"] = [e.model_dump(mode="json") for e in record.audit.entries]
    return out
