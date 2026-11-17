"""Rupee amount parsing that never raises and never guesses.

The v1 candidate matched ``rs`` anywhere, so "papers," became a currency
marker followed by an empty number and crashed with ``ValueError``.  Here a
currency marker must stand on its own (not inside a word), the number grammar
is validated, and malformed input yields a controlled ``MoneyMention`` with
``valid=False`` and an ``issue`` code.
"""
import re
from typing import List, Optional

from pydantic import BaseModel

_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_UNIT = r"(?:lakhs?|lacs?|crores?|cr|thousand|k)"
_PREFIX = re.compile(
    rf"(?<![A-Za-z0-9])(?P<marker>₹|rs\.?|inr|rupees?)[ \t]{{0,3}}(?P<number>{_NUMBER})"
    rf"(?:[ \t]?(?P<unit>{_UNIT})(?![A-Za-z]))?",
    re.I,
)
_SUFFIX = re.compile(
    rf"(?<![\w.,/\-₹])(?P<number>{_NUMBER})[ \t]?(?:(?P<unit>{_UNIT})[ \t]?)?(?P<marker>rupees?(?![A-Za-z])|inr(?![A-Za-z])|/-)",
    re.I,
)
_UNIT_ONLY = re.compile(rf"(?<![\w.,/\-₹])(?P<number>{_NUMBER})[ \t]?(?P<unit>lakhs?|lacs?|crores?)(?![A-Za-z])", re.I)
_MULTIPLIER = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
               "thousand": 1e3, "k": 1e3}
_WESTERN = re.compile(r"^\d{1,3}(?:,\d{3})+$")
_INDIAN = re.compile(r"^\d{1,2}(?:,\d{2})*,\d{3}$")
_PLAIN = re.compile(r"^\d+$")
_BARE_FIELD = re.compile(rf"^\s*(?:₹|rs\.?|inr|rupees?)?\s*(?P<number>{_NUMBER})\s*(?P<unit>{_UNIT})?\s*(?:/-|only|rupees?|inr)?\s*\.?\s*$", re.I)
_NIL = re.compile(r"^\s*(?:nil|none|zero|-+)\b", re.I)
MAX_RUPEES = 1e11  # anything larger is treated as a parsing artefact


class MoneyMention(BaseModel):
    raw: str
    value: Optional[float] = None     # rupees
    start: int = 0
    end: int = 0
    valid: bool = True
    issue: Optional[str] = None


def _to_value(number: str, unit: Optional[str]) -> (Optional[float], Optional[str]):
    whole, _, fraction = number.partition(".")
    if "," in whole and not (_WESTERN.match(whole) or _INDIAN.match(whole)):
        return None, "MALFORMED_GROUPING"
    if not _PLAIN.match(whole.replace(",", "")):
        return None, "NOT_A_NUMBER"
    try:
        value = float(whole.replace(",", "") + ("." + fraction if fraction else ""))
    except ValueError:
        return None, "NOT_A_NUMBER"
    value *= _MULTIPLIER.get((unit or "").lower().rstrip("."), 1)
    if value > MAX_RUPEES:
        return None, "OUT_OF_RANGE"
    return round(value, 2), None


def find_amounts(text: str) -> List[MoneyMention]:
    """All rupee amounts that carry an explicit currency marker or lakh/crore unit."""
    mentions, taken = [], []
    for pattern in (_PREFIX, _SUFFIX, _UNIT_ONLY):
        for match in pattern.finditer(text or ""):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            number = match.group("number").rstrip(",")
            value, issue = _to_value(number, match.groupdict().get("unit"))
            taken.append((match.start(), match.end()))
            mentions.append(MoneyMention(raw=match.group(0), value=value, start=match.start(), end=match.end(),
                                         valid=issue is None, issue=issue))
    return sorted(mentions, key=lambda item: item.start)


def parse_amount_field(value: str) -> MoneyMention:
    """Parse the value of a field already known to be monetary (e.g. a table cell).

    Accepts a bare number; rejects dates, identifiers, foreign currency and
    words.  Never raises.
    """
    text = (value or "").strip()
    if _NIL.match(text):
        return MoneyMention(raw=text, value=0.0)
    match = _BARE_FIELD.match(text)
    if not match:
        issue = "FOREIGN_CURRENCY" if re.match(r"^\s*(?:gbp|usd|eur|aud|cad|sgd|aed|£|\$|€)", text, re.I) else "NOT_AN_AMOUNT"
        return MoneyMention(raw=text, valid=False, issue=issue)
    amount, issue = _to_value(match.group("number").rstrip(","), match.group("unit"))
    return MoneyMention(raw=text, value=amount, valid=issue is None, issue=issue)


def format_inr(amount: float) -> str:
    digits = f"{int(round(amount))}"
    if len(digits) <= 3:
        return f"₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])
