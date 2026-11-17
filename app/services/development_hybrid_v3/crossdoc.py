"""Deterministic cross-document consistency checks (hybrid v3, development only).

Each finding sends the campaign to manual review (FLAG_FOR_REVIEW); none rejects it.

  DEATH_DATE_CONFLICT          two dates of death more than the tolerance apart (documents and campaign text)
  EVENT_DATE_CONFLICT          the campaign text dates a completed admission, discharge or procedure - or a scheduled
                               procedure - and the documents date the same kind of event, but none within the tolerance
  PATIENT_ID_CONFLICT          one identifier type (UHID, MRN, IP / OP number, patient ID, roll / enrolment / admission
                               number) has different values across documents that name the beneficiary
  AGE_CONFLICT / SEX_CONFLICT  the beneficiary's age (beyond the tolerance) or sex differs across the documents and
                               the campaign text
  TREATMENT_NOT_INDICATED      the campaign asks for a procedure that a document says is not indicated / not advised
  OUTSTANDING_AMOUNT_CONFLICT  documents from the same issuer state different outstanding amounts

Scope is deliberately narrow to limit false positives: several admissions or procedures can be genuine, so only
death dates are compared document-against-document.  What is not covered still depends on Gemini or on external
confirmation; see GEMINI_DEPENDENT.
"""
import re
from collections import defaultdict
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .config import SETTINGS
from .dates import DateAssessment

GEMINI_DEPENDENT = [
    "Contradictions in place, setting or circumstance (e.g. 'died at home' vs 'died in the ICU') unless a date also differs",
    "Treatment or course mismatches expressed with synonyms or different procedure names (beyond explicit "
    "'not indicated / not advised' statements)",
    "Diagnosis inconsistent with the requested treatment, or implausible clinical narratives",
    "Several admissions, discharges or procedures with different dates across documents (can be genuine)",
    "Relationship and identity claims not written as name / age / sex / identifier (e.g. 'my father' vs 'son of')",
    "Cost plausibility beyond V3's typical-range table; itemised arithmetic in free-form layouts",
    "Dates written in unusual formats, regional languages or without a year; scanned documents without text",
    "Narrative contradictions with no labelled field (e.g. the story says a fee is unpaid, a letter implies a scholarship)",
    "Fabricated but internally consistent documents: not detectable from text at all - only external confirmation",
]

_ID_LABELS = [("UHID", r"uhid"), ("MRN", r"mrn|medical\s+record\s+(?:no|number)"), ("IP_NO", r"i\.?p\.?\s*(?:no|number)"),
              ("OP_NO", r"o\.?p\.?\s*(?:no|number)"), ("PATIENT_ID", r"patient\s+id"),
              ("HOSPITAL_NO", r"hospital\s+(?:no|number)"), ("ROLL_NO", r"roll\s*(?:no|number)"),
              ("ENROLMENT_NO", r"enrol(?:l)?ment\s+(?:no|number)"), ("ADMISSION_NO", r"admission\s+(?:no|number)")]
_ID_RES = [(name, re.compile(rf"\b(?:{label})\b\.?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9/\-]{{2,}})", re.I)) for name, label in _ID_LABELS]
_AGE_SEX = re.compile(r"^\W{0,4}(\d{1,3})\s*(?:y(?:ea)?rs?\.?|yo)?\s*[/,]?\s*(m|f|male|female)\b", re.I)
_AGE_KEY = re.compile(r"^[^.;]{0,30}?\bage[d]?\s*[:\-]?\s*(\d{1,3})\b(?!\s*months?)", re.I)
_AGE_OLD = re.compile(r"^[^.;]{0,15}?\b(\d{1,3})[-\s]years?[-\s]old\b", re.I)
_AGE_COMMA = re.compile(r"^\s*,\s*(\d{1,3})\s*,")
_SEX_WORD = re.compile(r"^[^.;]{0,20}?\b(male|female)\b", re.I)
_PROCEDURE_FAMILIES = {
    "surgery": r"surger(?:y|ies)|surgical|operation|operative|bypass|cabg|replacement|\w+plasty|fixation|\w+ectomy|implant\w*",
    "revascularisation": r"revasculari[sz]ation|angioplasty|stent\w*|bypass|cabg|ptca",
    "transplant": r"transplant\w*",
    "chemotherapy": r"chemo\w*",
    "dialysis": r"dialysis|ha?emodialysis",
    "radiotherapy": r"radiotherapy|radiation\s+therapy",
}
_NEGATIONS = [
    re.compile(r"\bno\s+([^.;]{0,70}?)\s+(?:is\s+|are\s+)?(?:currently\s+)?(?:indicated|advised|required|recommended|needed|necessary)\b", re.I),
    re.compile(r"([^.;]{0,70}?)\s+(?:is\s+|are\s+)?not\s+(?:currently\s+)?(?:indicated|advised|required|recommended|needed|necessary)\b", re.I),
]
_CONSERVATIVE = re.compile(r"(?:conservative|non[- ]?operative|non[- ]?surgical)\s+(?:management|treatment)\s+(?:is\s+)?"
                           r"(?:advised|recommended|planned)|managed\s+conservatively", re.I)


class CrossFinding(BaseModel):
    code: str
    summary: str
    values: List[str] = Field(default_factory=list)
    basis: str = "DETERMINISTIC"


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").casefold()))


def _families(text: str) -> set:
    return {name for name, pattern in _PROCEDURE_FAMILIES.items() if re.search(rf"\b(?:{pattern})\b", text or "", re.I)}


def event_date_conflicts(dates: DateAssessment) -> List[CrossFinding]:
    tol = SETTINGS["date_conflict_tolerance_days"]
    findings = []
    deaths = [d for d in dates.dates if d.role == "death" and d.kind == "completed"]
    if deaths:
        lo, hi = min(deaths, key=lambda d: d.value), max(deaths, key=lambda d: d.value)
        if (hi.value - lo.value).days > tol:
            findings.append(CrossFinding(code="DEATH_DATE_CONFLICT",
                                         summary=f"Two dates of death: {lo.raw} ('{lo.document}') and {hi.raw} ('{hi.document}').",
                                         values=[f"{lo.document}: {lo.raw}", f"{hi.document}: {hi.raw}"]))
    for role, kind in (("admission", "completed"), ("discharge", "completed"), ("procedure", "completed"),
                       ("procedure", "scheduled")):
        claimed = [d for d in dates.dates if d.source == "campaign" and d.role == role and d.kind == kind]
        documented = [d for d in dates.dates if d.source == "document" and d.role == role
                      and (d.kind in ("completed", "mention") if kind == "completed" else d.kind == "scheduled")]
        for claim in claimed:
            if documented and all(abs((d.value - claim.value).days) > tol for d in documented):
                findings.append(CrossFinding(
                    code="EVENT_DATE_CONFLICT",
                    summary=f"The campaign dates the {role} {claim.raw}; the documents record "
                            + ", ".join(f"{d.raw} ('{d.document}')" for d in documented) + ".",
                    values=[f"Campaign text: {claim.raw}"] + [f"{d.document}: {d.raw}" for d in documented]))
    return findings


def identifier_conflicts(case: dict) -> List[CrossFinding]:
    name = _norm(case.get("beneficiary_name"))
    seen: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    for document in case.get("documents", []):
        text = document.get("content", "")
        if name and name not in _norm(text):
            continue                                    # only documents about the beneficiary
        for label, pattern in _ID_RES:
            for match in pattern.finditer(text):
                seen[label][match.group(1).upper().rstrip(".,;:")].append(document.get("title", ""))
    return [CrossFinding(code="PATIENT_ID_CONFLICT",
                         summary=f"Different {label.replace('_', ' ')} values for the beneficiary: " + ", ".join(values) + ".",
                         values=[f"{', '.join(sorted(set(docs)))}: {value}" for value, docs in values.items()])
            for label, values in seen.items() if len(values) > 1]


def _person_attributes(text: str, name: str) -> List[tuple]:
    """(age or None, sex or None) found right after each mention of the beneficiary's name."""
    out = []
    if not name.strip():
        return out
    pattern = re.compile(r"\b" + r"\s+".join(re.escape(part) for part in name.split()) + r"\b", re.I)
    for match in pattern.finditer(text or ""):
        window = text[match.end():match.end() + 60]
        age = sex = None
        m = _AGE_SEX.search(window)
        if m:
            age, sex = int(m.group(1)), m.group(2)[0].upper()
        else:
            for regex in (_AGE_KEY, _AGE_OLD, _AGE_COMMA):
                m = regex.search(window)
                if m:
                    age = int(m.group(1))
                    break
            s = _SEX_WORD.search(window)
            sex = s.group(1)[0].upper() if s else None
        if age is not None and not 0 < age <= 120:
            age = None
        if age is not None or sex is not None:
            out.append((age, sex))
    return out


def person_conflicts(case: dict) -> List[CrossFinding]:
    name = re.sub(r"^(?:mr|mrs|ms|shri|smt|dr|baby|master|kumari)\.?\s+", "", (case.get("beneficiary_name") or "").strip(), flags=re.I)
    sources = [("Campaign text", f"{case.get('title', '')}\n{case.get('story', '')}")]
    sources += [(d.get("title", ""), d.get("content", "")) for d in case.get("documents", [])]
    ages, sexes = defaultdict(set), defaultdict(set)
    for title, text in sources:
        for age, sex in _person_attributes(text, name):
            if age is not None:
                ages[age].add(title)
            if sex is not None:
                sexes[sex].add(title)
    findings = []
    if ages and max(ages) - min(ages) > SETTINGS["age_conflict_tolerance_years"]:
        findings.append(CrossFinding(code="AGE_CONFLICT", summary=f"The beneficiary's age differs: {sorted(ages)}.",
                                     values=[f"{', '.join(sorted(t))}: {a}" for a, t in sorted(ages.items())]))
    if len(sexes) > 1:
        findings.append(CrossFinding(code="SEX_CONFLICT", summary="The beneficiary's sex differs across records.",
                                     values=[f"{', '.join(sorted(t))}: {s}" for s, t in sorted(sexes.items())]))
    return findings


def treatment_conflicts(case: dict) -> List[CrossFinding]:
    claimed = _families(f"{case.get('title', '')} {case.get('story', '')}")
    findings = []
    for document in case.get("documents", []):
        text = document.get("content", "")
        negated = set()
        for regex in _NEGATIONS:
            for match in regex.finditer(text):
                negated |= _families(match.group(1))
        if _CONSERVATIVE.search(text):
            negated.add("surgery")
        overlap = claimed & negated
        if overlap:
            findings.append(CrossFinding(code="TREATMENT_NOT_INDICATED",
                                         summary=f"The campaign seeks {', '.join(sorted(overlap))}, but "
                                                 f"'{document.get('title')}' states it is not indicated or not advised.",
                                         values=[document.get("title", "")]))
    return findings


def amount_conflicts(case: dict, v3_result) -> List[CrossFinding]:
    by_issuer: Dict[str, List[tuple]] = defaultdict(list)
    for evidence in getattr(v3_result, "evidence", None) or []:
        balances = [float(f.value) for f in evidence.of("amount", "balance") if f.value is not None]
        if balances and evidence.issuer:
            by_issuer[evidence.issuer.casefold()].append((evidence.title, balances[-1]))
    findings = []
    for issuer, items in by_issuer.items():
        values = sorted({v for _, v in items})
        if len(values) > 1:
            lo, hi = values[0], values[-1]
            if hi - lo > max(SETTINGS["amount_conflict_min_inr"], SETTINGS["amount_conflict_tolerance"] * hi):
                findings.append(CrossFinding(code="OUTSTANDING_AMOUNT_CONFLICT",
                                             summary=f"Documents from the same issuer state different outstanding amounts.",
                                             values=[f"{t}: INR {v:,.0f}" for t, v in items]))
    return findings


def check(case: dict, v3_result, dates: DateAssessment) -> List[CrossFinding]:
    return (event_date_conflicts(dates) + identifier_conflicts(case) + person_conflicts(case)
            + treatment_conflicts(case) + amount_conflicts(case, v3_result))
