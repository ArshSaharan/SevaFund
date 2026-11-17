"""Financial-evidence gate (hybrid v3, development only).

A campaign may be approved only if a valid financial document establishes the amount requested.

Financial document: it is not a certificate, letter of enrolment, resolution, minutes, report, summary or
prescription, and either its type or title names a cost document (estimate, quotation, invoice, bill, fee demand /
notice / structure / statement, challan, cost schedule, budget, proforma, ledger, demand or debit note, work /
equipment / purchase order), or one of its first lines starts with such an instrument ("Equipment order QX-12 ...",
"Quotation No. ...").  A letter that merely mentions a figure in a sentence does not establish the amount.

Valid: it carries a payable amount (an outstanding balance after a payment / advance / cover, else a total, else
the sum of its itemised lines); it
is traceable (at least two of issuer, date, reference number, signatory); and none of its dates is expired or
future-dated (dates.py).

Supported: the goal does not exceed the documented need by more than `amount_support_tolerance`, using the
largest single document, or the sum over documents from different issuers.

Every other outcome is an information request (NEEDS_MORE_INFORMATION), never approval.  Large mismatches that
look like inflation are escalated separately by frozen V3 (AMOUNT_UNSUPPORTED, ALREADY_SETTLED ...).
"""
import re
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .config import SETTINGS
from .dates import DateAssessment

_ORDER = r"(?:work|purchase|equipment|fitting|service|supply)\s+order"
FINANCIAL_TYPE = re.compile(r"estimat|quot|invoice|\bbill\b|\bfees?\b|challan|\bcost|budget|proforma|ledger|"
                            r"student\s+account|fee\s+account|statement\s+of\s+account|demand\s+note|debit\s+note|costing|"
                            + _ORDER, re.I)
_INSTRUMENT_LINE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:final\s+)?(?:bill|invoice|estimate|quotation|quote|proforma|"
                              r"fee\s+(?:demand|notice|structure|statement)|cost\s+(?:estimate|schedule|sheet)|challan|"
                              r"demand\s+note|debit\s+note|" + _ORDER + r")\b", re.I | re.M)
NON_FINANCIAL = re.compile(r"certificate|bonafide|bona\s+fide|resolution|minutes|prescription|discharge\s+summary|"
                           r"\breport\b|enrol(?:l)?ment\s+(?:record|letter|proof)|identity|registration\s+(?:extract|record)|"
                           r"clinical\s+note", re.I)
_REFERENCE = re.compile(r"\b(?:no|number|ref|reference|record|file|order|invoice|bill|receipt|account|challan|quotation|"
                        r"estimate)\b\.?\s*[:#.]?\s*[A-Z0-9]*\d[A-Z0-9/\-]*|\b[A-Z]{2,}[A-Z0-9]*[-/][A-Z0-9/\-]*\d", re.I)
_ORG_WORDS = re.compile(r"hospital|clinic|centre|center|institute|college|school|university|academy|trust|society|"
                        r"association|committee|foundation|ltd|limited|pvt|services?|suppl(?:y|ies|iers)|traders|enterprises|"
                        r"pharmacy|board|office|department|corporation|panchayat|desk|bodies|works|labs?|diagnostics?|"
                        r"cooperative|federation|council|agency|store|motors", re.I)
_SIGNATORY = re.compile(r"\bsigned\b|signature|authori[sz]ed\s+signatory|headmaster|principal|registrar|accounts\s+officer|"
                        r"\bdr\.\s|consultant|manager|proprietor|secretary|treasurer", re.I)


class FinancialDocument(BaseModel):
    title: str
    issuer: Optional[str] = None
    need: Optional[float] = None
    basis: str = ""                 # balance | total | itemised | none
    traceability: int = 0
    problems: List[str] = Field(default_factory=list)   # EXPIRED | FUTURE_DATED | UNTRACEABLE | NO_AMOUNT

    @property
    def valid(self) -> bool:
        return not self.problems


class FinancialEvidence(BaseModel):
    status: str                     # SUPPORTED | MISSING | EXPIRED | FUTURE_DATED | UNTRACEABLE | NO_AMOUNT | INSUFFICIENT_AMOUNT
    goal: float
    documented_need: Optional[float] = None
    documents: List[FinancialDocument] = Field(default_factory=list)
    requests: List[str] = Field(default_factory=list)

    @property
    def supported(self) -> bool:
        return self.status == "SUPPORTED"


def is_financial(title: str, doc_type: str, text: str = "") -> bool:
    label = f"{(doc_type or '').replace('_', ' ')} {title or ''}"
    if NON_FINANCIAL.search(label):
        return False
    head = "\n".join((text or "").splitlines()[:6])
    return bool(FINANCIAL_TYPE.search(label) or _INSTRUMENT_LINE.search(head))


def _amounts(evidence) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {"balance": [], "total": [], "line_item": [], "paid": [], "covered": []}
    for field in evidence.of("amount"):
        if field.value is None or field.role not in out:
            continue
        raw = (field.raw or "").strip()
        if re.fullmatch(r"\d{4}", raw) and 1900 <= float(field.value) <= 2100:
            continue                                   # a year inside a date, not money
        out[field.role].append(float(Decimal(str(field.value))))
    return out


def _header(text: str) -> Optional[str]:
    """The issuer named at the top of the document, if any (placeholder tags such as "[Page 1]" are skipped)."""
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*(?:\[[^\]]*\]\s*)+", "", line).strip()
        if not line:
            continue
        candidate = line if len(line) <= 90 else re.split(r",|\s(?:confirms|certifies|states|records)\b", line)[0].strip()
        if _ORG_WORDS.search(candidate) and len(candidate) <= 90:
            return candidate
        if len(candidate) <= 60 and candidate[:1].isupper() and not re.search(r"\u20b9|rs\.?\s*\d|\d{3}", candidate, re.I):
            return candidate
        return None
    return None


def assess_financial(case: dict, v3_result, dates: DateAssessment) -> FinancialEvidence:
    """case: campaign input dict (documents with title / doc_type / content); v3_result: frozen V3 result."""
    goal = float(case.get("goal_amount") or 0)
    evidence = {e.index: e for e in (getattr(v3_result, "evidence", None) or [])}
    docs: List[FinancialDocument] = []
    for index, document in enumerate(case.get("documents", [])):
        title, doc_type, text = document.get("title", ""), document.get("doc_type", ""), document.get("content", "")
        if not is_financial(title, doc_type, text):
            continue
        ev = evidence.get(index)
        amounts = _amounts(ev) if ev is not None else {"balance": [], "total": [], "line_item": [], "paid": [], "covered": []}
        # A balance is the outstanding need only after a payment / advance / cover, or when no total is stated;
        # otherwise "balance" is a line-item label ("tuition fee balance Rs 21,500") and the total is the need.
        if amounts["balance"] and (amounts["paid"] or amounts["covered"] or not amounts["total"]):
            need, basis = amounts["balance"][-1], "balance"
        elif amounts["total"]:
            need, basis = max(amounts["total"]), "total"
        elif amounts["line_item"]:
            need, basis = sum(amounts["line_item"]), "itemised"
        else:
            need, basis = None, "none"
        issuer = (ev.issuer if ev is not None and ev.issuer else None) or _header(text)
        doc_dates = [d for d in dates.dates if d.document == title and d.source == "document"]
        signatory = bool(ev is not None and ev.of("person", "staff")) or bool(_SIGNATORY.search(text or ""))
        traceability = sum([bool(issuer), bool(doc_dates), bool(_REFERENCE.search(text or "")), signatory])
        problems = []
        if need is None:
            problems.append("NO_AMOUNT")
        if any(d.status == "FUTURE" for d in doc_dates):
            problems.append("FUTURE_DATED")
        if any(d.status == "EXPIRED" for d in doc_dates):
            problems.append("EXPIRED")
        if traceability < SETTINGS["min_financial_traceability"]:
            problems.append("UNTRACEABLE")
        docs.append(FinancialDocument(title=title, issuer=issuer, need=need, basis=basis, traceability=traceability,
                                      problems=problems))

    valid = [d for d in docs if d.valid]
    tolerance = 1 + SETTINGS["amount_support_tolerance"]
    if valid:
        largest = max(d.need for d in valid)
        by_issuer: Dict[str, float] = {}
        for d in valid:
            key = (d.issuer or d.title).casefold()
            by_issuer[key] = max(by_issuer.get(key, 0.0), d.need)
        documented = max(largest, sum(by_issuer.values()))
        if goal <= documented * tolerance and documented > 0:
            return FinancialEvidence(status="SUPPORTED", goal=goal, documented_need=documented, documents=docs)
        return FinancialEvidence(
            status="INSUFFICIENT_AMOUNT", goal=goal, documented_need=documented, documents=docs,
            requests=[f"The requested amount (INR {goal:,.0f}) is not covered by the cost documents (INR {documented:,.0f}). "
                      "Provide a quotation, estimate, bill or fee demand for the remaining amount."])
    if not docs:
        return FinancialEvidence(status="MISSING", goal=goal, documents=docs, requests=[
            "Provide a cost quotation, estimate, bill or fee demand from the institution or supplier showing the amount "
            "requested. A letter confirming enrolment or need does not establish the amount."])
    order = ["FUTURE_DATED", "EXPIRED", "NO_AMOUNT", "UNTRACEABLE"]
    status = next(p for p in order if any(p in d.problems for d in docs))
    requests = {
        "FUTURE_DATED": "A cost document carries a date after today; provide the genuine, current document.",
        "EXPIRED": "Provide a current version of the expired cost document: " + ", ".join(
            f"'{d.title}'" for d in docs if "EXPIRED" in d.problems) + ".",
        "NO_AMOUNT": "The cost document does not state a payable amount; provide an itemised quotation, estimate or bill.",
        "UNTRACEABLE": "Provide the cost document on the issuer's letterhead with its date and reference number.",
    }
    return FinancialEvidence(status=status, goal=goal, documents=docs, requests=[requests[status]])
