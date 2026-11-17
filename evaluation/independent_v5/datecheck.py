"""Independent date validation for authored cases (standard library only).

This parser is deliberately separate from the system under test: it never imports the V3, hybrid v2 or hybrid v3
date modules, so a date error in the system cannot also hide in the test data's validation."""
import re
from datetime import date, timedelta
from typing import List, Optional, Tuple

MONTHS = {name: i for i, names in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
     ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
     ("dec", "december")], start=1) for name in names}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
PATTERNS = [
    ("ymd", re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")),
    ("dmy", re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})\b")),
    ("d_mon_y", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-]+" + _MONTH + r"\.?[\s,\-]+(\d{4})\b", re.I)),
    ("mon_d_y", re.compile(r"\b" + _MONTH + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)),
]
ROLES = {"issue", "validity_end", "scheduled_event", "completed_event", "death", "other"}
PAST_ROLES = {"issue", "completed_event", "death"}


def _build(year: int, month: int, day: int) -> Optional[date]:
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse(raw: str) -> Optional[date]:
    """Parse one date string written in an Indian (day-first) convention."""
    found = find(raw)
    return found[0][1] if len(found) == 1 and found[0][0].strip() == raw.strip() else None


def find(text: str) -> List[Tuple[str, date]]:
    results, taken = [], []
    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text or ""):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            g = m.groups()
            if kind == "ymd":
                value = _build(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "dmy":
                value = _build(int(g[2]), int(g[1]), int(g[0]))
            elif kind == "d_mon_y":
                value = _build(int(g[2]), MONTHS[g[1].casefold().rstrip(".")], int(g[0]))
            else:
                value = _build(int(g[2]), MONTHS[g[0].casefold().rstrip(".")], int(g[1]))
            if value:
                results.append((m.group(0), value))
                taken.append((m.start(), m.end()))
    return results


def check_case(case: dict) -> Tuple[List[str], List[str]]:
    """Errors and warnings for the declared date facts of one case, relative to its own submission date."""
    errors, warnings = [], []
    data = case.get("input", {})
    try:
        submitted = date.fromisoformat(data.get("submitted_on", ""))
    except (TypeError, ValueError):
        return ["input.submitted_on must be an ISO date (YYYY-MM-DD)"], []
    if not isinstance(case.get("date_sensitive"), bool):
        errors.append("date_sensitive must be true or false")
    documents = {d.get("title"): d.get("content", "") for d in data.get("documents", [])}
    sources = {**documents, "STORY": data.get("story", "")}
    facts = case.get("date_facts") or []
    if not isinstance(facts, list):
        return errors + ["date_facts must be a list"], warnings
    for number, fact in enumerate(facts, start=1):
        label = f"date_facts[{number}]"
        if fact.get("role") not in ROLES:
            errors.append(f"{label}: role must be one of {sorted(ROLES)}")
            continue
        where = fact.get("document_title")
        if where not in sources:
            errors.append(f"{label}: document_title must name a document in this case, or STORY")
            continue
        written = fact.get("as_written", "")
        if not written or written not in sources[where]:
            errors.append(f"{label}: as_written '{written}' does not appear verbatim in '{where}'")
            continue
        try:
            declared = date.fromisoformat(fact.get("date", ""))
        except (TypeError, ValueError):
            errors.append(f"{label}: date must be an ISO date")
            continue
        parsed = parse(written)
        if parsed is None:
            errors.append(f"{label}: '{written}' is not a recognisable single date")
        elif parsed != declared:
            errors.append(f"{label}: '{written}' reads as {parsed.isoformat()}, not the declared {declared.isoformat()}")
        anomaly = fact.get("intentional_date_anomaly") is True
        if fact["role"] in PAST_ROLES and declared > submitted and not anomaly:
            errors.append(f"{label}: a {fact['role']} date after the submission date needs intentional_date_anomaly: true")
        if fact["role"] == "scheduled_event" and declared < submitted and not anomaly:
            warnings.append(f"{label}: scheduled event before the submission date")
        if fact["role"] == "validity_end" and declared < submitted and case.get("author_intended_label") == "legitimate" \
                and case.get("author_intended_documentation") == "complete":
            warnings.append(f"{label}: document expired before submission in a case declared legitimate and complete")
    if case.get("date_sensitive") and not any(f.get("role") in ROLES - {"issue", "other"} or
                                              f.get("intentional_date_anomaly") for f in facts):
        errors.append("a date_sensitive case needs at least one validity_end, scheduled_event, completed_event or "
                      "death fact, or an intentional anomaly")
    for title, text in sources.items():
        for raw, value in find(text):
            if value > submitted + timedelta(days=730) or value.year < 1950:
                warnings.append(f"'{raw}' in '{title}' is far from the submission date; check for a typo")
    return errors, warnings
