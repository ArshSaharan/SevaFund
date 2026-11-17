"""Hybrid v3 decision policy (development only).  Frozen V3 and frozen hybrid v2 are used, never modified.

Rules, first match wins.  Every decision records its triggers, reasons and - for reviews - a review basis.

  1  V3 VERIFICATION_ERROR                                        -> VERIFICATION_ERROR
  2  V3 REJECTED / FLAG_FOR_REVIEW, after V3's future-date findings are re-checked with the event-aware date model
     (a scheduled surgery or admission is not a future-issued document)
                                                                   -> same           DETERMINISTIC_FINDING
  3  a deterministic cross-document contradiction (crossdoc.py)   -> FLAG_FOR_REVIEW DETERMINISTIC_FINDING
  4  a future-dated document, or a future completed event in a record -> FLAG_FOR_REVIEW DETERMINISTIC_FINDING
  5  Gemini missing or failed                                     -> VERIFICATION_ERROR
  6  Gemini FLAG_FOR_REVIEW / REJECTED                            -> FLAG_FOR_REVIEW (never REJECTED)
        DOCUMENT_SUPPORTED_MODEL_FINDING when a concern is grounded in the documents, else UNVERIFIED_MODEL_SUSPICION
  7  a grounded Gemini contradiction or fraud indicator           -> FLAG_FOR_REVIEW DOCUMENT_SUPPORTED_MODEL_FINDING
  8  open evidence - expired document, financial evidence not established, a Gemini or V3 information request, an
     information gap or an unverified (ungrounded) concern        -> NEEDS_MORE_INFORMATION (every request listed)
  9  V3 APPROVED + Gemini APPROVED + financial evidence SUPPORTED + nothing open -> APPROVED
     APPROVED is never activation: the workflow makes it ELIGIBLE_PENDING_CONFIRMATION, authenticity stays
     UNCONFIRMED, and beneficiary, institution and payment destination must be confirmed independently.
 10  anything else                                                -> NEEDS_MORE_INFORMATION
"""
import re
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.services.development_gemini_verification.concerns import build_concerns
from app.services.development_verifier_v3 import verify_case
from app.services.development_verifier_v3.config import DEFAULT_CONFIG
from app.services.development_verifier_v3.decision import decide
from app.services.development_verifier_v3.normalize import find_dates
from app.services.development_verifier_v3.schemas import CaseInput, DocumentInput

from . import crossdoc
from .config import POLICY_VERSION
from .confirmation import start_record
from .dates import DateAssessment, assess, reclassify
from .financial import assess_financial

DETECT = {"FLAG_FOR_REVIEW", "REJECTED"}


class HybridV3Decision(BaseModel):
    decision: str
    workflow_state: str
    triggers: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    review_basis: Optional[str] = None       # DETERMINISTIC_FINDING | DOCUMENT_SUPPORTED_MODEL_FINDING | UNVERIFIED_MODEL_SUSPICION
    information_requests: List[str] = Field(default_factory=list)
    open_items: List[str] = Field(default_factory=list)     # unresolved evidence, whatever the decision
    unverified_concerns: List[str] = Field(default_factory=list)
    vetoed_concerns: List[str] = Field(default_factory=list)
    cross_document_findings: List[dict] = Field(default_factory=list)
    financial_evidence: dict = Field(default_factory=dict)
    v3_decision: str = ""
    v3_effective_decision: str = ""
    refuted_v3_findings: List[str] = Field(default_factory=list)
    authenticity: str = "UNCONFIRMED"
    required_confirmations: List[str] = Field(default_factory=list)
    policy_version: str = POLICY_VERSION


def v3_case(case: dict) -> CaseInput:
    submitted = date.fromisoformat(case["submitted_on"]) if case.get("submitted_on") else None
    return CaseInput(title=case["title"], category=case["category"], story=case["story"], goal_amount=case["goal_amount"],
                     goal_currency=case.get("goal_currency", "INR"), beneficiary_name=case.get("beneficiary_name"),
                     beneficiary_type=case.get("beneficiary_type"), city=case.get("city"), state=case.get("state"),
                     submitted_on=submitted,
                     documents=[DocumentInput(title=d["title"], doc_type=d["doc_type"], text=d.get("content", ""))
                                for d in case.get("documents", [])])


AMOUNT_CODES = {"AMOUNT_UNSUPPORTED", "AMOUNT_EXCEEDS_BALANCE"}


def _year_inside_date(text: str, shown: str) -> bool:
    """True when an 'amount' is a four-digit year that only ever occurs inside a date in the document."""
    digits = re.sub(r"\D", "", shown or "")
    if len(digits) != 4 or not 1900 <= int(digits) <= 2100:
        return False
    occurrences = [m.start() for m in re.finditer(rf"(?<!\d){digits}(?!\d)", text or "")]
    spans = [(start, end) for _value, start, end, _raw in find_dates(text or "")]
    return bool(occurrences) and all(any(start <= o < end for start, end in spans) for o in occurrences)


def effective_v3(v3_result, case: dict, reference: date):
    """Re-check two kinds of frozen-V3 finding that come from misread dates, drop the refuted ones and re-run V3's
    own frozen decision rule on the rest:
      FUTURE_DATED_DOCUMENT  whose date is a scheduled or mentioned event, not a future issue / completed record
      AMOUNT_UNSUPPORTED / AMOUNT_EXCEEDS_BALANCE  whose documented figure is the year of a date (e.g. '/2026')"""
    documents = case.get("documents", [])
    kept, refuted = [], []
    for finding in v3_result.findings:
        if finding.code in AMOUNT_CODES:
            years = [v for v in finding.values if 0 <= v.doc_index < len(documents)
                     and _year_inside_date(documents[v.doc_index].get("content", ""), v.value)]
            if years:
                refuted.append(f"{finding.summary} -> '{years[0].value}' is the year of a date in "
                               f"'{years[0].document}', not an amount")
                continue
        if finding.code == "FUTURE_DATED_DOCUMENT":
            value = next((v for v in finding.values if 0 <= v.doc_index < len(documents)), None)
            if value is not None:
                doc = documents[value.doc_index]
                occurrences = reclassify(doc.get("content", ""), value.value, doc.get("title", ""),
                                         doc.get("doc_type", ""), reference)
                if occurrences and all(o.status != "FUTURE" for o in occurrences):
                    refuted.append(f"{finding.summary} -> '{value.value}' is a {occurrences[0].kind} date, "
                                   "not a future-issued record")
                    continue
        kept.append(finding)
    if not refuted:
        return v3_result.decision.value, [], list(v3_result.information_requests)
    readable = sum(1 for e in (v3_result.evidence or []) if e.readable)
    recomputed = decide(kept, v3_result.requirements, v3_result.errors, DEFAULT_CONFIG, readable)
    return recomputed.decision.value, refuted, list(recomputed.information_requests)


def combine(case: dict, v3_result, gemini: Optional[dict], evidence_chunks: List[dict], reference: date) -> HybridV3Decision:
    """case: campaign input dict; gemini: {status, decision, concerns / red_flag_texts, missing_requirements} or None."""
    campaign_text = " ".join(str(case.get(k) or "") for k in ("title", "story", "beneficiary_name", "city", "state"))
    dates: DateAssessment = assess([(d.get("title", ""), d.get("content", ""), d.get("doc_type", ""))
                                    for d in case.get("documents", [])], reference,
                                   campaign_text=f"{case.get('title', '')}\n{case.get('story', '')}")
    v3_raw = v3_result.decision.value
    v3_eff, refuted, v3_requests = effective_v3(v3_result, case, reference)
    cross = crossdoc.check(case, v3_result, dates)
    financial = assess_financial(case, v3_result, dates)
    gemini_ok = bool(gemini) and gemini.get("status", "OK") == "OK" and bool(gemini.get("decision"))
    concerns = build_concerns(gemini, evidence_chunks, campaign_text, dates) if gemini_ok else []
    grounded = [c for c in concerns if c.escalates]
    unverified = [c.text for c in concerns if c.type in ("FRAUD_INDICATOR", "CONTRADICTION") and not c.grounded]
    vetoed = [f"{c.text} - {c.veto_reason}" for c in concerns if c.vetoed]
    gaps = [c.text for c in concerns if c.type == "INFORMATION_GAP"]

    open_items: List[str] = []
    for d in dates.expired:
        open_items.append(f"Provide a current version of '{d.document}' (expired: {d.raw}).")
    if not financial.supported:
        open_items.extend(financial.requests)
    if gemini_ok and gemini["decision"] == "NEEDS_MORE_INFORMATION":
        open_items.extend(gemini.get("missing_requirements") or [])
    if v3_eff == "NEEDS_MORE_INFORMATION":
        open_items.extend(v3_requests or ["Provide the essential document identified by the offline verifier."])
    open_items.extend(gaps)
    open_items.extend(f"Clarify (unverified model concern): {u}" for u in unverified)
    open_items = list(dict.fromkeys(i for i in open_items if i))

    def result(decision, trigger, reason, basis=None):
        record = start_record(decision, case.get("category", "OTHER"), case.get("beneficiary_type"),
                              open_items if decision == "NEEDS_MORE_INFORMATION" else ())
        return HybridV3Decision(
            decision=decision, workflow_state=record.state.value, triggers=[trigger], reasons=[reason], review_basis=basis,
            information_requests=open_items if decision == "NEEDS_MORE_INFORMATION" else [], open_items=open_items,
            unverified_concerns=unverified, vetoed_concerns=vetoed,
            cross_document_findings=[f.model_dump() for f in cross], financial_evidence=financial.model_dump(),
            v3_decision=v3_raw, v3_effective_decision=v3_eff, refuted_v3_findings=refuted,
            required_confirmations=[r.check.value for r in record.required_confirmations])

    if v3_eff == "VERIFICATION_ERROR":
        return result("VERIFICATION_ERROR", "V3_ERROR", "The offline verifier did not complete.")
    if v3_eff in DETECT:
        return result(v3_eff, "V3_CONTRADICTION", "The offline verifier found a material contradiction.",
                      "DETERMINISTIC_FINDING")
    if cross:
        return result("FLAG_FOR_REVIEW", "CROSS_DOCUMENT_CONTRADICTION:" + ",".join(sorted({f.code for f in cross})),
                      cross[0].summary, "DETERMINISTIC_FINDING")
    if dates.future:
        first = dates.future[0]
        return result("FLAG_FOR_REVIEW", "FUTURE_DATED_DOCUMENT",
                      f"'{first.document}' records {first.raw} ({first.kind}), after today {reference.isoformat()}.",
                      "DETERMINISTIC_FINDING")
    if not gemini_ok:
        category = (gemini or {}).get("failure_category") or "NOT_RUN"
        return result("VERIFICATION_ERROR", f"GEMINI_FAILED:{category}",
                      "Gemini verification did not complete; the campaign cannot be approved until it is re-run.")
    if gemini["decision"] in DETECT:
        if grounded:
            return result("FLAG_FOR_REVIEW", "GEMINI_EXPLICIT_WARNING",
                          f"Gemini recommended review; document-supported: {grounded[0].text}",
                          "DOCUMENT_SUPPORTED_MODEL_FINDING")
        return result("FLAG_FOR_REVIEW", "GEMINI_EXPLICIT_WARNING",
                      "Gemini recommended review or rejection without a quote found in the documents; this is an "
                      "unverified model suspicion for a reviewer to check, not a finding.", "UNVERIFIED_MODEL_SUSPICION")
    if grounded:
        return result("FLAG_FOR_REVIEW", "GROUNDED_MODEL_CONTRADICTION",
                      f"A contradiction tied to the documents was raised: {grounded[0].text}",
                      "DOCUMENT_SUPPORTED_MODEL_FINDING")
    if open_items:
        trigger = ("EXPIRED_DOCUMENT" if dates.expired else
                   f"FINANCIAL_EVIDENCE_{financial.status}" if not financial.supported else
                   "GEMINI_INFORMATION_REQUEST" if gemini["decision"] == "NEEDS_MORE_INFORMATION" else
                   "V3_INFORMATION_REQUEST" if v3_eff == "NEEDS_MORE_INFORMATION" else "UNRESOLVED_INFORMATION_GAP")
        return result("NEEDS_MORE_INFORMATION", trigger, "Evidence is incomplete; this is not a fraud finding.")
    if v3_eff == "APPROVED" and gemini["decision"] == "APPROVED" and financial.supported:
        return result("APPROVED", "ALL_CHECKS_PASS",
                      "Documents are consistent and the amount is documented. Consistency is not proof of authenticity: "
                      "the beneficiary, the institution and the payment destination must be confirmed independently "
                      "before activation.")
    return result("NEEDS_MORE_INFORMATION", "UNRESOLVED",
                  f"Unhandled combination V3={v3_eff}, Gemini={gemini.get('decision')}; not approved.")


def assess_case(case: dict, gemini: Optional[dict], evidence_chunks: List[dict], reference: date) -> HybridV3Decision:
    return combine(case, verify_case(v3_case(case), DEFAULT_CONFIG), gemini, evidence_chunks, reference)
