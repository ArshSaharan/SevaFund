"""Event-aware document-date interpretation (hybrid v3, development only).

Every date is given a kind from the words that introduce it:
  validity   an explicit expiry ("valid until", "expires on")
  issue      the date the document was issued ("Date:", "dated", "Bill date", "issued on", an unlabelled header date)
  scheduled  a planned event ("proposed date of surgery", "scheduled for", "will be admitted on", "due by")
  completed  an event recorded as having happened ("discharged on", "who expired on", "date of discharge" in a
             retrospective record such as a discharge summary, bill, receipt, report or certificate)
  mention    any other date (an event named without tense, an unlabelled date in the body)
plus relative validity: "valid for 60 days", "valid for one year from the date of issue".

Statuses against the caller's reference date (today in Asia/Kolkata):
  FUTURE     an issue date, or a completed-event date in a document, after reference + grace days
  EXPIRED    a validity date (explicit or relative) before the reference date, or a time-sensitive document
             (cost, fee, income, enrolment or prescription document) issued more than max_document_age_days ago
  VALID / SCHEDULED / MENTIONED otherwise.  Scheduled and mentioned dates are never judged as future-dated.

Difference from frozen V3's extractor: a date introduced by "date of <event>" or "<event> date" (surgery,
admission, appointment ...) is an event date, never the document's issue date, and a planned event in the future
is legitimate.  Frozen V3 is not modified; its future-date findings are re-checked with `reclassify`.
"""
import re
from datetime import date, timedelta
from typing import Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.services.development_verifier_v3.normalize import find_dates

from .config import SETTINGS

_BREAK = re.compile(r"[.;\n]|\s[-–—]\s")
_ROLE_TERMS = [
    ("death", r"death|died|expired|passed\s+away|demise|deceased"),
    ("discharge", r"discharg\w*"),
    ("admission", r"admission|admitted|admit"),
    ("procedure", r"surger(?:y|ies)|surgical|operation|operated|procedure|\w+plasty|\w+ectomy|\w+otomy|transplant\w*|"
                  r"implant\w*|replacement|repair|bypass|angioplasty|fixation"),
    ("payment", r"paid|payment|received|remitted"),
]
_ROLE_RE = re.compile("|".join(f"(?P<{name}>\\b(?:{pattern})\\b)" for name, pattern in _ROLE_TERMS), re.I)
_OTHER_EVENT = (r"appointment|review|follow[- ]?up|check(?:-?up)?|visit|consultation|session|sitting|examinations?|exams?|"
                r"semester|term|classes|joining|commencement|travel|departure|delivery|installation|due|deadline|hearing|"
                r"meeting|interview|scan|dialysis|chemotherapy|cycle|therapy|camp|test")
_EVENT_NOUNS = (r"surgery|operation|procedure|admission|discharge|death|payment|appointment|review|follow[- ]?up|"
                r"check(?:-?up)?|visit|consultation|session|examination|exam|semester|term|joining|commencement|travel|"
                r"departure|delivery|installation|due|hearing|meeting|interview|scan|dialysis|chemotherapy|transplant|"
                r"implant|test")
_OTHER_EVENT_RE = re.compile(rf"\b(?:{_OTHER_EVENT})\b", re.I)
_EVENT_DATE_LABEL = re.compile(rf"(?:\bdate\s+of\s+(?:the\s+)?(?:{_EVENT_NOUNS})|\b(?:{_EVENT_NOUNS})\s+date)\s*[:\-]?\s*$", re.I)
_VALIDITY = re.compile(r"(?:valid\s+(?:until|till|up\s*to|upto|through|thru)|expir(?:es|y|ing|ed)(?:\s+on)?(?:\s+date)?|"
                       r"validity(?:\s+(?:date|until|till|up\s*to))?)\s*[:\-]?\s*$", re.I)
_ISSUE = re.compile(r"(?:\bdated|\bdate\s*[:\-]|\bdate\s+of\s+(?:issue|registration|report|bill|invoice|letter)|"
                    r"\bissued(?:\s+on)?|\b(?:bill|invoice|report|statement|letter|estimate|receipt|quotation|notice|"
                    r"certificate|challan|registration|order)\s+date|\bprepared(?:\s+on)?|\bas\s+on|\bdt\.?)\s*[:\-]?\s*$",
                    re.I)
_PLANNING = re.compile(r"\b(?:proposed|scheduled|planned|plans?|expected|tentative(?:ly)?|next|upcoming|due|deadline|"
                       r"to\s+be|will|shall|likely|fixed\s+for|booked|on\s+or\s+before|appointment|follow[- ]?up)\b", re.I)
_PAST = re.compile(r"\b(?:discharged|admitted|operated|performed|underwent|undergone|expired|died|passed\s+away|paid|"
                   r"received|held|conducted|completed|delivered|remitted|was|were|had|has\s+been)\b", re.I)
_COMPLETION_LABEL = re.compile(r"(?:\bdate\s+of\s+(?:discharge|death|surgery|operation|procedure|admission|payment|delivery)|"
                               r"\b(?:discharge|death|surgery|operation|admission|payment)\s+date)\s*[:\-]?\s*$", re.I)
_RETROSPECTIVE_DOC = re.compile(r"discharge|final\s+bill|\bbill\b|invoice|receipt|death|birth|operation\s+note|report|"
                                r"case\s+summary|certificate|record", re.I)
_TIME_SENSITIVE_DOC = re.compile(r"estimat|quot|invoice|\bbill\b|\bfee|challan|\bcost|budget|income|bonafide|enrol|"
                                 r"offer|admission\s+letter|prescription", re.I)
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "six": 6, "twelve": 12}
_RELATIVE = re.compile(r"valid\s+(?:for\s+)?(\d{1,3}|one|two|three|four|six|twelve)\s+(days?|months?|years?)", re.I)


class DocumentDate(BaseModel):
    document: str
    raw: str
    value: date
    kind: str                    # issue | validity | relative_validity | scheduled | completed | mention
    role: Optional[str] = None   # death | discharge | admission | procedure | payment
    status: str                  # VALID | EXPIRED | FUTURE | SCHEDULED | MENTIONED
    source: str = "document"     # document | campaign


class DateAssessment(BaseModel):
    reference_date: date
    dates: List[DocumentDate] = Field(default_factory=list)

    @property
    def future(self) -> List[DocumentDate]:
        return [d for d in self.dates if d.status == "FUTURE" and d.source == "document"]

    @property
    def expired(self) -> List[DocumentDate]:
        return [d for d in self.dates if d.status == "EXPIRED" and d.source == "document"]


def _role(clause: str) -> Optional[str]:
    last = None
    for match in _ROLE_RE.finditer(clause):
        last = match
    return last.lastgroup if last else None


def classify(text: str, start: int, retrospective: bool, header: bool) -> Tuple[str, Optional[str]]:
    """(kind, role) of the date starting at `start` in `text`."""
    line_start = text.rfind("\n", 0, start) + 1
    context = text[max(line_start, start - 90):start]
    clause = _BREAK.split(context)[-1]
    role = _role(clause)
    if _VALIDITY.search(context):
        return "validity", None
    if _EVENT_DATE_LABEL.search(context):
        if _PLANNING.search(clause):
            return "scheduled", role
        if retrospective and _COMPLETION_LABEL.search(context):
            return "completed", role
        return "mention", role
    if _ISSUE.search(context):
        return "issue", None
    if role or _OTHER_EVENT_RE.search(clause):
        if _PLANNING.search(clause):
            return "scheduled", role
        if _PAST.search(clause):
            return "completed", role
        return "mention", role
    if header:
        return "issue", None
    return "mention", None


def _relative_expiry(text: str, issued: Optional[date]) -> Optional[Tuple[date, str]]:
    match = _RELATIVE.search(text or "")
    if not match or issued is None:
        return None
    count = int(match.group(1)) if match.group(1).isdigit() else _NUMBER_WORDS[match.group(1).lower()]
    unit = match.group(2).lower()
    days = count * (1 if unit.startswith("day") else 30 if unit.startswith("month") else 365)
    return issued + timedelta(days=days), match.group(0)


def assess_text(title: str, text: str, doc_type: str, reference: date, source: str = "document",
                grace_days: Optional[int] = None, max_age_days: Optional[int] = None) -> List[DocumentDate]:
    grace = SETTINGS["date_grace_days"] if grace_days is None else grace_days
    max_age = SETTINGS["max_document_age_days"] if max_age_days is None else max_age_days
    text = text or ""
    label = f"{(doc_type or '').replace('_', ' ')} {title or ''}"
    retrospective = source == "document" and bool(_RETROSPECTIVE_DOC.search(label))
    time_sensitive = source == "document" and bool(_TIME_SENSITIVE_DOC.search(label))
    header_end = len("\n".join(text.split("\n")[:2])) if source == "document" else -1
    out: List[DocumentDate] = []
    for value, start, _end, raw in find_dates(text):
        kind, role = classify(text, start, retrospective, header=start <= header_end)
        if kind == "validity":
            status = "EXPIRED" if value < reference else "VALID"
        elif kind == "issue":
            if value > reference + timedelta(days=grace):
                status = "FUTURE"
            elif time_sensitive and value < reference - timedelta(days=max_age):
                status = "EXPIRED"
            else:
                status = "VALID"
        elif kind == "completed":
            status = "FUTURE" if source == "document" and value > reference + timedelta(days=grace) else "VALID"
        elif kind == "scheduled":
            status = "SCHEDULED"
        else:
            status = "MENTIONED"
        out.append(DocumentDate(document=title, raw=raw, value=value, kind=kind, role=role, status=status, source=source))
    if source == "document":
        issued = next((d.value for d in out if d.kind == "issue"), None)
        relative = _relative_expiry(text, issued)
        if relative:
            expiry, raw = relative
            out.append(DocumentDate(document=title, raw=raw, value=expiry, kind="relative_validity", role=None,
                                    status="EXPIRED" if expiry < reference else "VALID", source=source))
    return out


def assess(documents: Iterable[Tuple[str, str, str]], reference: date, campaign_text: str = "") -> DateAssessment:
    """documents: (title, text, doc_type).  Campaign text is classified too (for cross-document comparison) but
    is never judged future-dated or expired - campaigns legitimately describe planned events."""
    dates: List[DocumentDate] = []
    for title, text, doc_type in documents:
        dates.extend(assess_text(title, text, doc_type, reference))
    if campaign_text:
        dates.extend(assess_text("Campaign text", campaign_text, "CAMPAIGN", reference, source="campaign"))
    return DateAssessment(reference_date=reference, dates=dates)


def reclassify(text: str, raw: str, title: str, doc_type: str, reference: date) -> List[DocumentDate]:
    """Every occurrence of `raw` in a document, classified with the event-aware rules."""
    return [d for d in assess_text(title, text, doc_type, reference) if d.raw == raw]
