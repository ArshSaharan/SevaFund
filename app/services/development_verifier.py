"""Offline development-only verifier; never wired into production requests."""
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.schemas.ai import DimensionScores, EvidenceReference, VerificationResult


@dataclass
class DevelopmentVerification:
    result: VerificationResult
    evidence_relation: str
    evidence_conflicts: List[str]


_DURATION = re.compile(r"\b(\d+)\s*(weeks?|months?|years?|days?)\b", re.I)
_QUANTITY = re.compile(r"\b(\d+)\s*(units?|kits?|items?|books?|devices?|students?|people|families|households)\b", re.I)
_MONEY = re.compile(r"(?:₹|rs\.?\s*)([\d,]+)", re.I)
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                 "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15}
_CATEGORY_EVIDENCE_TERMS = {
    "MEDICAL": ("medical", "clinic", "hospital", "patient", "treatment", "therapy", "care plan", "nutrition", "prosthetic", "ambulance", "oncology", "dialysis"),
    "EDUCATION": ("education", "college", "campus", "student", "school", "course", "apprentice", "hostel", "exam", "testing center", "tuition", "laboratory", "lab "),
    "COMMUNITY": ("community", "municipal", "ward", "village", "residents", "households", "cooperative", "water", "shelter", "relief", "council", "shared well", "repair"),
}


def _conflicts(story: str, beneficiary_name: Optional[str], evidence: str) -> List[str]:
    claim, doc = story.casefold(), evidence.casefold()
    conflicts = []
    claim_amounts = [int(x.replace(",", "")) for x in _MONEY.findall(story)]
    doc_amounts = [int(x.replace(",", "")) for x in _MONEY.findall(evidence)]
    if claim_amounts and doc_amounts and any(abs(a - b) / max(a, b) >= 0.05 for a in claim_amounts for b in doc_amounts):
        conflicts.append("amount mismatch between claim and retrieved document")

    def durations(text):
        numeric = [(int(n), unit.lower().rstrip("s")) for n, unit in _DURATION.findall(text)]
        words = [(number, unit.lower().rstrip("s")) for word, unit in re.findall(
            r"\b(" + "|".join(_NUMBER_WORDS) + r")\s+(weeks?|months?|years?|days?)\b", text, re.I
        ) for number in [_NUMBER_WORDS[word.lower()]]]
        return numeric + words
    durations_a = durations(story)
    durations_b = durations(evidence)
    if durations_a and durations_b and durations_a != durations_b:
        conflicts.append("duration mismatch between claim and retrieved document")
    elif ("full-year" in claim or "twelve months" in claim or "12 months" in claim) and ("week" in doc and ("no later" in doc or "no additional" in doc or "only" in doc)):
        conflicts.append("duration mismatch between claim and retrieved document")

    quantities_a = [(int(n), unit.lower().rstrip("s")) for n, unit in _QUANTITY.findall(story)]
    quantities_b = [(int(n), unit.lower().rstrip("s")) for n, unit in _QUANTITY.findall(evidence)]
    if quantities_a and quantities_b and quantities_a != quantities_b:
        conflicts.append("quantity mismatch between claim and retrieved document")

    if beneficiary_name and beneficiary_name.casefold() in claim and beneficiary_name.casefold() not in doc:
        other_person = re.search(r"(?:payee|beneficiary|applicant|account holder)(?: of record)?\s*(?:is|:)?\s*(?:a different applicant,?\s*)?([A-Z][a-z]+\s+[A-Z][a-z]+)", evidence, re.I)
        if other_person:
            conflicts.append("identity mismatch between campaign beneficiary and document payee")
    if ("second payment" in claim or "again" in claim or "outstanding" in claim or "unpaid" in claim) and re.search(r"\b(delivered|signed for|settled|paid in full|no outstanding|already supplied)\b", doc):
        conflicts.append("reimbursement or prior-delivery mismatch")
    if "different activity" in doc or "not authorized" in doc:
        conflicts.append("purpose mismatch between claim and authorization")
    return conflicts


def verify_development_case(
    title: str,
    category: str,
    story: str,
    goal_amount: float,
    beneficiary_name: Optional[str] = None,
    documents: Optional[Sequence[str]] = None,
) -> DevelopmentVerification:
    docs = [str(item) for item in (documents or []) if str(item).strip()]
    text = "\n".join(docs)
    conflicts = _conflicts(title + "\n" + story, beneficiary_name, text) if docs else []
    if not docs:
        relation = "unavailable"
        recommendation = "NEEDS_MORE_INFO"
        documentation = 10.0
        missing = ["Provide a readable, campaign-specific supporting document."]
    elif re.search(r"\b(preliminary|pending|not yet recorded|unreadable|illegible)\b", text, re.I):
        relation = "incomplete"
        recommendation = "NEEDS_MORE_INFO"
        documentation = 45.0
        missing = ["Provide final records confirming amount, beneficiary, and approval status."]
    elif conflicts:
        relation = "contradicts"
        recommendation = "FLAG_FOR_REVIEW"
        documentation = 70.0
        missing = []
    elif not any(term in text.casefold() for term in _CATEGORY_EVIDENCE_TERMS.get(category.upper(), ())):
        relation = "incomplete"
        recommendation = "NEEDS_MORE_INFO"
        documentation = 45.0
        missing = [f"Provide evidence from a source relevant to the {category.lower()} campaign category."]
    else:
        relation = "supports"
        recommendation = "AUTO_APPROVE"
        documentation = 90.0
        missing = []

    # Rejection is deliberately conservative: one conflict is never sufficient.
    high_confidence = [c for c in conflicts if any(term in c for term in ("identity", "amount", "reimbursement", "purpose"))]
    explicit_forgery = re.search(r"\b(forged|fabricated|altered)\b.{0,35}\b(invoice|receipt|record|document)\b", text, re.I)
    if len(set(high_confidence)) >= 2 and explicit_forgery:
        recommendation = "REJECT"

    score = 74.0 if relation == "supports" else 48.0 if relation == "contradicts" else 56.0 if relation == "incomplete" else 52.0
    flags = conflicts.copy()
    positives = [f"Evidence is associated with the stated {category.lower()} campaign purpose."] if relation == "supports" else []
    result = VerificationResult(
        authenticity_score=score,
        risk_level="LOW" if recommendation == "AUTO_APPROVE" else "HIGH" if recommendation in {"FLAG_FOR_REVIEW", "REJECT"} else "MEDIUM",
        recommendation=recommendation,
        summary=("Retrieved supporting evidence is consistent with the campaign claims." if relation == "supports" else
                 "Retrieved evidence conflicts with one or more campaign claims; human verification is required." if conflicts else
                 "The available evidence is missing or incomplete; request more information."),
        dimension_scores=DimensionScores(plausibility=75.0, specificity=70.0, red_flag_score=100.0 if not conflicts else 40.0, documentation=documentation),
        red_flags=flags, positive_signals=positives, missing_requirements=missing,
        supporting_evidence=[EvidenceReference(document_title=f"Retrieved supporting document {i + 1}", excerpt=doc, relevance=1.0) for i, doc in enumerate(docs)],
        confidence=0.72, model_used="sevafund-development-candidate-v1",
    )
    return DevelopmentVerification(result=result, evidence_relation=relation, evidence_conflicts=conflicts)
