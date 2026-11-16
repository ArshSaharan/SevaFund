"""Normalization and tolerant comparison of names, organisations, IDs and dates.

Comparisons return a verdict rather than a boolean so that callers can tell a
genuine contradiction (MISMATCH) from a harmless formatting difference (MATCH)
and from something that cannot be decided from the text (PARTIAL / UNKNOWN).
"""
import re
from datetime import date
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

MATCH, PARTIAL, MISMATCH, UNKNOWN = "MATCH", "PARTIAL", "MISMATCH", "UNKNOWN"

HONORIFICS = {"mr", "mrs", "ms", "miss", "master", "shri", "sri", "smt", "kumari", "kum", "dr", "baby", "late",
              "tmt", "thiru", "sr", "prof", "mx", "shrimati", "sau", "km"}
_MONTHS = {name: number for number, names in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
     ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
     ("dec", "december")], start=1) for name in names}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_PATTERNS = [
    (re.compile(r"(?<![\w/.\-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\w/\-])"), "ymd"),
    (re.compile(r"(?<![\w/.\-])(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?![\w/\-])"), "dmy"),
    (re.compile(rf"(?<![\w/\-])(\d{{1,2}})(?:st|nd|rd|th)?[\s\-]+({_MONTH_RE})\.?,?[\s\-]+(\d{{4}})\b", re.I), "dMy"),
    (re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I), "Mdy"),
]


def find_dates(text: str) -> List[Tuple[date, int, int, str]]:
    """Return (date, start, end, raw) for every unambiguous calendar date.

    Day-first order is assumed for numeric dates, the Indian convention.
    Impossible dates (31/02/2026) are skipped rather than raised.
    """
    found, taken = [], []
    for pattern, order in _DATE_PATTERNS:
        for match in pattern.finditer(text or ""):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            a, b, c = match.groups()
            try:
                if order == "ymd":
                    value = date(int(a), int(b), int(c))
                elif order == "dmy":
                    value = date(int(c), int(b), int(a))
                elif order == "dMy":
                    value = date(int(c), _MONTHS[b.lower()], int(a))
                else:
                    value = date(int(c), _MONTHS[a.lower()], int(b))
            except (ValueError, KeyError):
                continue
            if not 1900 <= value.year <= 2100:
                continue
            taken.append((match.start(), match.end()))
            found.append((value, match.start(), match.end(), match.group(0)))
    return sorted(found, key=lambda item: item[1])


# ------------------------------------------------------------------ names
_GIVEN_NAME_ABBREVIATIONS = {"mohd": "mohammad", "md": "mohammad", "mohamed": "mohammad",
                             "muhammad": "mohammad", "mohammed": "mohammad"}
_TRANSLITERATION = [("ksh", "ks"), ("x", "ks"), ("sh", "s"), ("ph", "f"), ("th", "t"), ("dh", "d"), ("bh", "b"),
                    ("kh", "k"), ("gh", "g"), ("jh", "j"), ("ch", "c"), ("w", "v"), ("ee", "i"), ("oo", "u"),
                    ("aa", "a"), ("ou", "u"), ("y", "i")]


def name_tokens(name: str) -> List[str]:
    text = re.sub(r"\(.*?\)", " ", name or "")
    tokens = re.findall(r"[a-z]+", text.casefold())
    return [_GIVEN_NAME_ABBREVIATIONS.get(t, t) for t in tokens if t not in HONORIFICS]


def skeleton(token: str) -> str:
    """Spelling skeleton that absorbs common romanisation variants of Indian
    names (Lakshmi/Laxmi, Sheela/Shila, Vijay/Vijai)."""
    text = token
    for source, target in _TRANSLITERATION:
        text = text.replace(source, target)
    return re.sub(r"(.)\1+", r"\1", text)


def _similar(left: str, right: str, threshold: float = 0.84) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 4:
        return False
    if len(left) >= 4 and skeleton(left) == skeleton(right):
        return True
    return SequenceMatcher(None, left, right).ratio() >= threshold


def _token_equal(left: str, right: str) -> Tuple[bool, bool]:
    """(equal, full) - `full` is False when the match relies on an initial."""
    if len(left) == 1 or len(right) == 1:
        return left[0] == right[0], False
    return _similar(left, right), True


def compare_names(left: str, right: str) -> Tuple[str, float, str]:
    """Compare two person names.  Returns (verdict, confidence, note).

    Tolerates honorifics, case, token order, initials, a dropped middle name
    and minor transliteration differences.  A shared given name with a
    different surname is PARTIAL (maiden/older family name is plausible); a
    shared surname with a different given name is a MISMATCH (a relative).
    """
    a, b = name_tokens(left), name_tokens(right)
    if not a or not b:
        return UNKNOWN, 0.0, "name not readable"
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    remaining, full_matches, matched = list(long_), 0, 0
    for token in short:
        for candidate in remaining:
            equal, full = _token_equal(token, candidate)
            if equal:
                remaining.remove(candidate)
                matched += 1
                full_matches += full
                break
    if matched == len(short):
        if full_matches == 0:
            return PARTIAL, 0.4, "only initials agree"
        if len(short) == 1 and len(long_) > 1:
            return PARTIAL, 0.5, "only a single name is given in one place"
        exact = a == b
        return MATCH, 1.0 if exact else 0.9, "same name" if exact else "same name in a different format"
    shared = [t for t in short if len(t) > 1 and any(_similar(t, other) for other in long_ if len(other) > 1)]
    if shared:
        if _token_equal(a[0], b[0])[0] and len(a) > 1 and len(b) > 1:
            return PARTIAL, 0.5, "same given name with a different surname"
        return MISMATCH, 0.8, "different given name; only a family name is shared"
    return MISMATCH, 0.95, "no part of the name is shared"


# --------------------------------------------------------- organisations
_ORG_ABBREVIATIONS = {"hosp": "hospital", "inst": "institute", "govt": "government", "engg": "engineering",
                      "univ": "university", "coll": "college", "st": "saint", "dept": "department",
                      "tech": "technology", "sch": "school", "intl": "international", "natl": "national",
                      "centre": "center", "org": "organisation", "organization": "organisation", "med": "medical"}
_ORG_STOP = {"the", "of", "and", "for", "pvt", "ltd", "private", "limited", "at", "in", "m", "s", "llp", "regd"}
ORG_GENERIC = {"hospital", "college", "institute", "university", "school", "trust", "foundation", "society",
               "samiti", "mandal", "sangh", "samuh", "sangam", "club", "association", "committee", "center",
               "clinic", "academy", "charitable", "public", "government", "medical", "sciences", "research",
               "general", "national", "international", "memorial", "welfare", "group", "organisation", "saint",
               "shri", "sri", "shree", "department", "multispeciality", "speciality", "sangha", "samithi",
               "kendra", "mandali", "samaj", "manch", "polytechnic"}


def org_tokens(name: str) -> List[str]:
    text = (name or "").casefold().replace("&", " and ")
    text = re.sub(r"\b([a-z])\.\s*(?=[a-z]\b)", r"\1", text)     # "g.v." / "g. v." -> "gv"
    text = re.sub(r"'s\b", "", text)
    tokens = [_ORG_ABBREVIATIONS.get(t, t) for t in re.findall(r"[a-z0-9]+", text)]
    return [t for t in tokens if t not in _ORG_STOP]


def _is_acronym(token: str, tokens: List[str]) -> bool:
    if not 2 <= len(token) <= 6:
        return False
    initials = "".join(t[0] for t in tokens)
    return token in initials


def compare_orgs(left: str, right: str) -> Tuple[str, float, str]:
    a, b = org_tokens(left), org_tokens(right)
    da, db = [t for t in a if t not in ORG_GENERIC], [t for t in b if t not in ORG_GENERIC]
    if not da or not db:
        if a and b and a == b:
            return MATCH, 0.8, "same organisation name"
        return UNKNOWN, 0.0, "organisation name too generic to compare"

    def covered(tokens: List[str], other_distinct: List[str], other_all: List[str]) -> int:
        count = 0
        for token in tokens:
            if any(_similar(token, o, 0.85) or (len(token) >= 3 and o.startswith(token)) or
                   (len(o) >= 3 and token.startswith(o)) for o in other_distinct):
                count += 1
            elif _is_acronym(token, other_all):
                count += 1
        return count

    share = max(covered(da, db, b) / len(da), covered(db, da, a) / len(db))
    if share >= 0.99:
        return MATCH, 0.9, "same organisation"
    if share >= 0.6:
        return MATCH, 0.75, "organisation names largely agree"
    if share == 0:
        return MISMATCH, 0.85, "organisation names share no distinctive word"
    return PARTIAL, 0.5, "organisation names agree only in part"


# -------------------------------------------------------------- identifiers
def normalize_id(value: str) -> str:
    """Upper-case, drop separators and zero-padding of each numeric segment
    (SMH/2026/00123 == smh-2026-123)."""
    segments = re.split(r"[^A-Za-z0-9]+", value or "")
    cleaned = []
    for segment in segments:
        segment = re.sub(r"(?<=[A-Za-z])0+(?=\d)", "", segment)
        if segment.isdigit():
            segment = segment.lstrip("0") or "0"
        cleaned.append(segment.upper())
    return "".join(cleaned)


def mask(value: Optional[str], keep: int = 3) -> str:
    """Redact a private value for logs, keeping only its length and tail."""
    text = str(value or "")
    if len(text) <= keep:
        return "*" * len(text)
    return "*" * (len(text) - keep) + text[-keep:]
