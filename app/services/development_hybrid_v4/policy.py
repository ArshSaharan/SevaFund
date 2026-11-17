"""Hybrid v4 decision policy (development only).

Hybrid v4 = frozen hybrid v3 (unchanged, called as a function) + three additions:

  1  PAYMENT_ACCOUNT_CONFLICT (payment.py): conflicting bank details across documents -> FLAG_FOR_REVIEW
     (DETERMINISTIC_FINDING).  Like hybrid v3's other deterministic checks it does not need Gemini, so it also
     applies when Gemini failed.
  2  Assisted cost route: a NEEDS_MORE_INFORMATION whose every open item concerns formal cost evidence is marked
     ASSISTED_COST_CONFIRMATION, so a caseworker can obtain the amount from the cost issuer instead of the applicant
     having to produce a quotation.  The request lists acceptable alternative evidence.
  3  Explanation and audit: every decision carries findings with their basis and document evidence, a plain-language
     explanation, the case fingerprint, and the policy and settings versions.  The workflow (workflow.py) adds the
     fourth required confirmation (AMOUNT) and the hash-chained audit log.

Unchanged from hybrid v3 (and re-tested): Gemini can never cause REJECTED (only frozen V3's deterministic
multi-contradiction rule can); a Gemini concern escalates only when its quote is found in the retrieved documents;
otherwise it is reported as an unverified model suspicion; date interpretation uses hybrid v3's event-aware model;
APPROVED is never activation.
"""
import re
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.services.development_gemini_verification.concerns import build_concerns
from app.services.development_hybrid_v3 import assess as assess_dates
from app.services.development_hybrid_v3 import combine as hybrid_v3_combine
from app.services.development_hybrid_v3 import v3_case
from app.services.development_verifier_v3 import verify_case
from app.services.development_verifier_v3.config import DEFAULT_CONFIG

from . import payment
from .audit import case_fingerprint
from .config import POLICY_VERSION, REQUIRED_CHECKS, SETTINGS, digest
from .workflow import ASSISTED_COST_CONFIRMATION

DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}
_COST_ITEM = re.compile(r"cost|quot|estimat|invoice|\bbill|fee|amount|payable|financial|budget|price|expense|challan|"
                        r"demand|receipt", re.I)
_NOT_COST = re.compile(r"identity|aadhaar|\bid\b|proof\s+of\s+(?:identity|relationship|enrol)|diagnos|prescription|"
                       r"registration|death|admission\s+letter|bonafide|consent|clarify \(unverified", re.I)
ALTERNATIVE_COST_EVIDENCE = {
    "MEDICAL": "If the hospital does not issue formal quotations (for example a government hospital), you can send "
               "instead: the hospital's list of items to buy with pharmacy quotes, the doctor's note naming the "
               "procedure, an insurance or PMJAY pre-authorisation, or recent receipts for ongoing treatment. A "
               "caseworker can also obtain the amount directly from the hospital's billing desk.",
    "EDUCATION": "Instead of a fee demand you can send: the official fee structure or prospectus page, last term's "
                 "receipt with the current circular, or a scholarship letter showing the balance. A caseworker can "
                 "also obtain the amount directly from the institution's accounts office.",
    "COMMUNITY": "Instead of a formal quotation you can send: two supplier quotations, the government schedule of rates "
                 "for the items, or invoices from a comparable earlier project. A caseworker can also obtain the "
                 "amount directly from the supplier or contractor.",
}


class Finding(BaseModel):
    source: str        # V3_DETERMINISTIC | CROSS_DOCUMENT | DATE | PAYMENT_ACCOUNT | GEMINI_GROUNDED | GEMINI_UNVERIFIED
    code: str
    text: str
    evidence: List[dict] = Field(default_factory=list)     # [{"document": ..., "quote": ...}]


class HybridV4Decision(BaseModel):
    decision: str
    triggers: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    review_basis: Optional[str] = None
    information_requests: List[str] = Field(default_factory=list)
    manual_route: Optional[str] = None
    findings: List[Finding] = Field(default_factory=list)
    explanation: str = ""
    required_confirmations: List[str] = Field(default_factory=list)
    hybrid_v3_decision: str = ""
    hybrid_v3_triggers: List[str] = Field(default_factory=list)
    v3_decision: str = ""
    reference_date: str = ""
    case_fingerprint: str = ""
    policy_version: str = POLICY_VERSION
    settings_digest: str = Field(default_factory=digest)

    def audit_payload(self) -> dict:
        return self.model_dump(mode="json")


def _v3_findings(v3_result, refuted: List[str]) -> List[Finding]:
    out = []
    for f in v3_result.findings:
        if any(f.summary and r.startswith(f.summary) for r in refuted):
            continue
        out.append(Finding(source="V3_DETERMINISTIC", code=f.code or f.kind, text=f.summary,
                           evidence=[{"document": v.document, "quote": f"{v.field}: {v.value}"} for v in f.values]))
    return out


def _gemini_findings(case: dict, gemini: Optional[dict], chunks: List[dict], reference: date) -> List[Finding]:
    if not gemini or gemini.get("status", "OK") != "OK" or not gemini.get("decision"):
        return []
    campaign_text = " ".join(str(case.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state"))
    dates = assess_dates([(d.get("title", ""), d.get("content", ""), d.get("doc_type", "")) for d in case.get("documents", [])],
                         reference, campaign_text=f"{case.get('title', '')}\n{case.get('story', '')}")
    out = []
    for c in build_concerns(gemini, chunks, campaign_text, dates):
        if c.type not in ("FRAUD_INDICATOR", "CONTRADICTION") or c.vetoed:
            continue
        evidence = [{"document": c.document or "", "quote": c.evidence_quote}] if c.grounded and c.evidence_quote else []
        out.append(Finding(source="GEMINI_GROUNDED" if c.grounded else "GEMINI_UNVERIFIED", code=c.type, text=c.text,
                           evidence=evidence))
    return out


def _cost_only(open_items: List[str]) -> bool:
    return bool(open_items) and all(_COST_ITEM.search(i) and not _NOT_COST.search(i) for i in open_items)


def _explain(decision: str, basis: Optional[str], reasons: List[str], findings: List[Finding], requests: List[str],
             route: Optional[str]) -> str:
    lines = [f"Decision: {decision}."]
    lines += [f"Reason: {r}" for r in reasons]
    if decision in DETECT:
        lines.append(f"Basis: {basis}. This is a referral for human review, not a fraud determination.")
        for f in findings:
            where = "; ".join(f"'{e.get('document')}': \"{e.get('quote')}\"" for e in f.evidence) or "no document quote"
            lines.append(f"Finding [{f.source}/{f.code}]: {f.text} Evidence: {where}.")
    elif decision == "NEEDS_MORE_INFORMATION":
        lines += [f"Request: {r}" for r in requests]
        if route == ASSISTED_COST_CONFIRMATION:
            lines.append("Assisted route available: a caseworker can confirm the amount with the cost issuer; all four "
                         "independent checks still apply before activation.")
    elif decision == "APPROVED":
        lines.append("Provisional only. Before activation, confirm independently: " + ", ".join(REQUIRED_CHECKS) + ".")
    else:
        lines.append("No approval is possible until verification completes.")
    return "\n".join(lines)


def decide(case: dict, v3_result, gemini: Optional[dict], chunks: List[dict], reference: date) -> HybridV4Decision:
    hv3 = hybrid_v3_combine(case, v3_result, gemini, chunks, reference)          # frozen, unchanged
    decision, triggers, reasons, basis = hv3.decision, list(hv3.triggers), list(hv3.reasons), hv3.review_basis
    requests, route = list(hv3.information_requests), None

    findings = _v3_findings(v3_result, hv3.refuted_v3_findings) if hv3.v3_effective_decision in DETECT else []
    findings += [Finding(source="CROSS_DOCUMENT", code=f["code"], text=f["summary"],
                         evidence=[{"document": "", "quote": v} for v in f.get("values", [])])
                 for f in hv3.cross_document_findings]
    if triggers and triggers[0] == "FUTURE_DATED_DOCUMENT":
        future = assess_dates([(d.get("title", ""), d.get("content", ""), d.get("doc_type", ""))
                               for d in case.get("documents", [])], reference).future
        findings.append(Finding(source="DATE", code="FUTURE_DATED_DOCUMENT", text=reasons[0],
                                evidence=[{"document": d.document, "quote": d.raw} for d in future]))
    gemini_findings = _gemini_findings(case, gemini, chunks, reference)

    conflicts = payment.check(case)
    gemini_failed_only = decision == "VERIFICATION_ERROR" and triggers and triggers[0].startswith("GEMINI_FAILED")
    if conflicts and (decision in ("APPROVED", "NEEDS_MORE_INFORMATION") or gemini_failed_only):
        decision, basis, requests = "FLAG_FOR_REVIEW", "DETERMINISTIC_FINDING", []
        triggers = ["PAYMENT_ACCOUNT_CONFLICT"] + triggers          # hybrid v3's own decision stays in hybrid_v3_*
        reasons = [f"Conflicting bank details: {conflicts[0].summary}"]
    findings += [Finding(source="PAYMENT_ACCOUNT", code=c.code, text=c.summary, evidence=c.evidence) for c in conflicts]

    # Every Gemini concern is shown with its source label: GEMINI_GROUNDED (quote found in the documents) or
    # GEMINI_UNVERIFIED (no quote found; for the reviewer to check, never evidence by itself).
    findings += gemini_findings
    if decision in DETECT and basis == "UNVERIFIED_MODEL_SUSPICION" and not gemini_findings:
        findings.append(Finding(source="GEMINI_UNVERIFIED", code="MODEL_RECOMMENDATION", text=reasons[0]))

    if decision == "NEEDS_MORE_INFORMATION" and SETTINGS["assisted_cost_route"] and _cost_only(hv3.open_items) \
            and not hv3.unverified_concerns:
        route = ASSISTED_COST_CONFIRMATION
        category = (case.get("category") or "").upper()
        alternative = next((v for k, v in ALTERNATIVE_COST_EVIDENCE.items() if k[:4] in category),
                           ALTERNATIVE_COST_EVIDENCE["COMMUNITY"])
        requests = requests + [alternative]

    if decision == "APPROVED":
        reasons = ["Documents are consistent and the amount is documented. Consistency is not proof of authenticity: the "
                   "beneficiary, the institution, the payment destination and the amount must each be confirmed "
                   "independently before activation."]
    if decision == "REJECTED" and hv3.v3_effective_decision != "REJECTED":
        raise AssertionError("REJECTED may only come from frozen V3's deterministic rule")   # defensive invariant
    return HybridV4Decision(
        decision=decision, triggers=triggers, reasons=reasons, review_basis=basis if decision in DETECT else None,
        information_requests=requests if decision == "NEEDS_MORE_INFORMATION" else [], manual_route=route,
        findings=findings, explanation=_explain(decision, basis, reasons, findings, requests, route),
        required_confirmations=list(REQUIRED_CHECKS) if decision == "APPROVED" else [],
        hybrid_v3_decision=hv3.decision, hybrid_v3_triggers=list(hv3.triggers), v3_decision=hv3.v3_decision,
        reference_date=reference.isoformat(), case_fingerprint=case_fingerprint(case))


def assess_case(case: dict, gemini: Optional[dict], chunks: List[dict], reference: date) -> HybridV4Decision:
    return decide(case, verify_case(v3_case(case), DEFAULT_CONFIG), gemini, chunks, reference)
