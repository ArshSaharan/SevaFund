"""Improved V3 + Gemini escalation policy (hybrid v2, development only).

Rules, first match wins.  Every decision records its trigger codes and reasons.

  1  V3 VERIFICATION_ERROR                                  -> VERIFICATION_ERROR   V3_ERROR
  2  V3 REJECTED / FLAG_FOR_REVIEW                          -> same                 V3_CONTRADICTION
  3  a document issue date after the reference date          -> FLAG_FOR_REVIEW      FUTURE_DATED_DOCUMENT
  4  Gemini missing or failed                                -> VERIFICATION_ERROR   GEMINI_FAILED:<category>
  5  Gemini decision FLAG_FOR_REVIEW / REJECTED              -> FLAG_FOR_REVIEW      GEMINI_EXPLICIT_FRAUD_WARNING
     (Gemini alone never rejects; a reviewer decides)
  6  a grounded fraud indicator or contradiction             -> FLAG_FOR_REVIEW      GROUNDED_CONTRADICTION
     (even when Gemini only asked for more information)
  7  an expired document                                     -> NEEDS_MORE_INFORMATION  EXPIRED_DOCUMENT
  8  Gemini NEEDS_MORE_INFORMATION                           -> NEEDS_MORE_INFORMATION  GEMINI_INFORMATION_REQUEST
  9  V3 NEEDS_MORE_INFORMATION                               -> NEEDS_MORE_INFORMATION  V3_INFORMATION_REQUEST
 10  Gemini approved but raised information gaps or an       -> NEEDS_MORE_INFORMATION  UNRESOLVED_INFORMATION_GAP
     unverified (ungrounded) fraud-type concern
 11  V3 APPROVED and Gemini APPROVED, nothing unresolved     -> APPROVED             BOTH_APPROVE
     APPROVED is never activation: the approval workflow turns it into ELIGIBLE_PENDING_CONFIRMATION, and
     beneficiary, payment-destination and institution confirmation remain mandatory before any funds move.

What changed from the frozen hybrid (v1): a generic warning attached to an information request no longer
escalates (it becomes part of the information request); ungrounded fraud-type concerns are shown to the
reviewer but cannot escalate on their own; model claims about future dates are checked against document dates.
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.services.development_approval_workflow import AutomatedOutcome, start

from .concerns import Concern, build_concerns
from .config import POLICY_VERSION
from .dates import DateAssessment

DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}


class CombinedDecision(BaseModel):
    decision: str
    workflow_state: str
    triggers: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    information_requests: List[str] = Field(default_factory=list)
    unverified_concerns: List[str] = Field(default_factory=list)   # ungrounded fraud-type concerns, for the reviewer
    vetoed_concerns: List[str] = Field(default_factory=list)
    policy_version: str = POLICY_VERSION


def combine(v3_decision: str, gemini: Optional[dict], evidence_chunks: List[dict], campaign_text: str,
            dates: Optional[DateAssessment], category: str = "OTHER", beneficiary_type: Optional[str] = "SELF",
            v3_information_requests: Optional[List[str]] = None) -> CombinedDecision:
    """gemini: a dict with status (OK/FAILED), decision, red_flag_texts or concerns, missing_requirements;
    None means Gemini was not run (treated as a failure)."""
    concerns: List[Concern] = []
    if gemini and gemini.get("status", "OK") == "OK":
        concerns = build_concerns(gemini, evidence_chunks, campaign_text, dates)
    unverified = [c.text for c in concerns if c.type in ("FRAUD_INDICATOR", "CONTRADICTION") and not c.grounded]
    vetoed = [f"{c.text} — {c.veto_reason}" for c in concerns if c.vetoed]

    def result(decision, trigger, reason, requests=()):
        state = start(AutomatedOutcome(decision=decision, category=category, beneficiary_type=beneficiary_type)).state.value
        return CombinedDecision(decision=decision, workflow_state=state, triggers=[trigger], reasons=[reason],
                                information_requests=list(dict.fromkeys(r for r in requests if r)),
                                unverified_concerns=unverified, vetoed_concerns=vetoed)

    if v3_decision == "VERIFICATION_ERROR":
        return result("VERIFICATION_ERROR", "V3_ERROR", "The offline verifier did not complete.")
    if v3_decision in DETECT:
        return result(v3_decision, "V3_CONTRADICTION", "The offline verifier found a material contradiction.")
    if dates is not None and dates.future:
        first = dates.future[0]
        return result("FLAG_FOR_REVIEW", "FUTURE_DATED_DOCUMENT",
                      f"'{first.document}' is dated {first.value.isoformat()}, after the reference date "
                      f"{dates.reference_date.isoformat()}.")
    if not gemini or gemini.get("status", "OK") != "OK" or not gemini.get("decision"):
        category_code = (gemini or {}).get("failure_category") or "NOT_RUN"
        return result("VERIFICATION_ERROR", f"GEMINI_FAILED:{category_code}",
                      "Gemini verification did not complete; the campaign cannot be approved until it is re-run.")
    if gemini["decision"] in DETECT:
        grounded = [c.text for c in concerns if c.escalates]
        return result("FLAG_FOR_REVIEW", "GEMINI_EXPLICIT_FRAUD_WARNING",
                      "Gemini explicitly recommended review or rejection"
                      + (f"; grounded evidence: {grounded[0]}" if grounded else "; no grounded quote — reviewer to verify."))
    escalating = [c for c in concerns if c.escalates]
    if escalating:
        return result("FLAG_FOR_REVIEW", "GROUNDED_CONTRADICTION",
                      f"A contradiction tied to the documents was raised: {escalating[0].text}")
    gap_requests = [c.text for c in concerns if c.type == "INFORMATION_GAP"]
    if dates is not None and dates.expired:
        doc = dates.expired[0]
        return result("NEEDS_MORE_INFORMATION", "EXPIRED_DOCUMENT",
                      f"'{doc.document}' is expired or out of date ({doc.raw}).",
                      [f"Provide a current version of '{doc.document}'."] + gap_requests)
    if gemini["decision"] == "NEEDS_MORE_INFORMATION":
        return result("NEEDS_MORE_INFORMATION", "GEMINI_INFORMATION_REQUEST",
                      "Gemini asked for more information; its warnings are information gaps, not fraud findings.",
                      list(gemini.get("missing_requirements") or []) + gap_requests)
    if v3_decision == "NEEDS_MORE_INFORMATION":
        return result("NEEDS_MORE_INFORMATION", "V3_INFORMATION_REQUEST",
                      "The offline verifier is missing essential evidence.", list(v3_information_requests or []))
    if gap_requests or unverified:
        return result("NEEDS_MORE_INFORMATION", "UNRESOLVED_INFORMATION_GAP",
                      "Gemini approved but raised information gaps or an unverified concern that must be resolved first.",
                      gap_requests + [f"Clarify: {u}" for u in unverified])
    if v3_decision == "APPROVED" and gemini["decision"] == "APPROVED":
        return result("APPROVED", "BOTH_APPROVE",
                      "V3 and Gemini both approve; independent confirmation is still required before activation.")
    return result("NEEDS_MORE_INFORMATION", "UNRESOLVED", f"Unhandled combination V3={v3_decision}, "
                                                          f"Gemini={gemini.get('decision')}; not approved.")
