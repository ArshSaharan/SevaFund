"""Deterministic document-date assessment against an explicit reference date.

The model is told the current date (prompt.py), but the decision never relies on the model's sense of time:
every document date is classified here, and model claims about "future" dates are checked against it.

Statuses
  VALID      issue date on or before the reference date (and not older than the maximum age)
  EXPIRED    a "valid until / expires" date before the reference date, or an issue date older than the maximum age
  FUTURE     an issue date later than reference + grace days (a record of something that has not happened yet)
  MENTIONED  a date describing a planned, scheduled or due event; legitimately in the future, never judged
"""
import re
from datetime import date, timedelta
from typing import Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.services.development_verifier_v3.normalize import find_dates

from .config import SETTINGS

_VALIDITY = re.compile(r"(valid\s+(?:until|till|up\s*to|through|thru)|expir(?:es|y|ing|ed)?(?:\s+on)?(?:\s+date)?|"
                       r"validity)\s*[:\-]?\s*$", re.I)
_ISSUE = re.compile(r"(dated|date\s*[:\-]|date\s+of\s+issue|issued(?:\s+on)?|prepared(?:\s+on)?|recorded(?:\s+on)?|"
                    r"(?:bill|invoice|report|statement|letter|estimate|receipt)\s+date\s*[:\-]?|as\s+on|\bdt\.?\s*[:\-]?)\s*$", re.I)
# An event keyword must sit immediately before the date ("due on 30/10/2026", "scheduled for 2 Dec 2026").
_EVENT = re.compile(r"(due(?:\s+(?:on|by|date))?|payable\s+by|on\s+or\s+before|before|scheduled(?:\s+(?:for|on))?|"
                    r"planned(?:\s+(?:for|on))?|appointment(?:\s+on)?|next\s+\w+(?:\s+on)?|starting(?:\s+on)?|"
                    r"commenc\w*(?:\s+on)?|deadline|admission\s+on|sitting\s+on|session\s+on|visit\s+on|from|until|till)"
                    r"\s*[:\-]?\s*$", re.I)
_FUTURE_CLAIM = re.compile(r"future[- ]?dated|future\s+date|dated\s+in\s+the\s+future|date\s+(?:is|lies|falls)\s+in\s+the\s+"
                           r"future|post[- ]?dated|(?:has|have)\s+not\s+(?:yet\s+)?occurred", re.I)


class DocumentDate(BaseModel):
    document: str
    raw: str
    value: date
    kind: str            # issue | validity | event | unlabelled
    status: str          # VALID | EXPIRED | FUTURE | MENTIONED


class DateAssessment(BaseModel):
    reference_date: date
    dates: List[DocumentDate] = Field(default_factory=list)

    @property
    def future(self) -> List[DocumentDate]:
        return [d for d in self.dates if d.status == "FUTURE"]

    @property
    def expired(self) -> List[DocumentDate]:
        return [d for d in self.dates if d.status == "EXPIRED"]


def _kind(context: str, line_start: bool) -> str:
    if _VALIDITY.search(context):
        return "validity"
    if _EVENT.search(context):
        return "event"
    if _ISSUE.search(context) or line_start:
        return "issue"
    return "unlabelled"


def assess_dates(documents: Iterable[Tuple[str, str]], reference_date: date,
                 grace_days: Optional[int] = None, max_age_days: Optional[int] = None) -> DateAssessment:
    """documents: (title, text) pairs.  Unlabelled dates are treated as issue dates only for the FUTURE test
    when they appear in a document header (first two lines); otherwise they are MENTIONED."""
    grace = SETTINGS["date_grace_days"] if grace_days is None else grace_days
    max_age = SETTINGS["max_document_age_days"] if max_age_days is None else max_age_days
    out = []
    for title, text in documents:
        text = text or ""
        header_end = len("\n".join(text.split("\n")[:2]))
        for value, start, _end, raw in find_dates(text):
            line_start_index = text.rfind("\n", 0, start) + 1
            context = text[max(line_start_index, start - 40):start]
            kind = _kind(context, line_start=not text[line_start_index:start].strip())
            if kind == "unlabelled" and start <= header_end:
                kind = "issue"
            if kind == "validity":
                status = "EXPIRED" if value < reference_date else "VALID"
            elif kind == "issue":
                if value > reference_date + timedelta(days=grace):
                    status = "FUTURE"
                elif value < reference_date - timedelta(days=max_age):
                    status = "EXPIRED"
                else:
                    status = "VALID"
            else:
                status = "MENTIONED"
            out.append(DocumentDate(document=title, raw=raw, value=value, kind=kind, status=status))
    return DateAssessment(reference_date=reference_date, dates=out)


def claims_future_date(text: str) -> bool:
    return bool(_FUTURE_CLAIM.search(text or ""))
