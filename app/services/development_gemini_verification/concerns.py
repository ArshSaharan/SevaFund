"""Separate Gemini's explicit fraud warnings from ordinary information requests.

Every concern Gemini raises becomes a `Concern` with a type:
  FRAUD_INDICATOR  forged/altered documents, already-paid or settled costs, another person's record, diverted payee
  CONTRADICTION    a stated conflict between the campaign and its documents (discrepancy, mismatch, contradicts ...)
  INFORMATION_GAP  missing, unverified, pending or vague information - a reason to ask, not to accuse
  DATE_CLAIM       a claim that a document is future-dated or expired - checked against dates.py
  OTHER            anything else (never escalates on its own)

Structured concerns (the dated prompt asks the model to categorise each one and quote the evidence) are used
when present; production-schema outputs (free-text `red_flags`) fall back to a transparent text classifier.

A FRAUD_INDICATOR or CONTRADICTION is *grounded* only if it is tied to the retrieved documents:
  structured  its evidence quote is found in the retrieved text (exact, or >= 80% token overlap)
  free text   it names a retrieved document or cites a number / distinctive word that occurs in the retrieved
              text but not in the campaign's own text (title, story, beneficiary, location)
Ungrounded fraud-type concerns are reported to the reviewer but cannot escalate a campaign by themselves.
"""
import re
from typing import Iterable, List, Optional

from pydantic import BaseModel

from .config import SETTINGS
from .dates import DateAssessment, claims_future_date

FRAUD = re.compile(
    r"forg(?:ed|ery)|fabricat|tamper|doctored|\balter(?:ed|ation)\b|counterfeit|\bfake\b|duplicate\s+(?:claim|request|campaign|"
    r"funding|invoice|bill)|double[- ]fund|already\s+(?:been\s+)?(?:fully\s+)?(?:paid|settled|funded|covered|reimbursed|"
    r"cleared)|paid\s+in\s+full|fully\s+paid|account\s+(?:is\s+|was\s+)?closed|balance\s+(?:is\s+|of\s+)?(?:nil|zero|₹\s*0)|"
    r"(?:nil|zero)\s+(?:outstanding\s+)?balance|"
    r"belongs?\s+to\s+(?:a\s+)?(?:different|another)|different\s+(?:patient|person|beneficiary|student|individual|name)|"
    r"third[- ]party\s+(?:account|payee)|unrelated\s+(?:individual|person|account)|diverted|impersonat", re.I)
CONTRADICTION = re.compile(r"contradict|discrepan|mismatch|inconsisten|does\s+not\s+match|do\s+not\s+match|"
                           r"conflicts?\s+with|conflicting|differs?\s+from|does\s+not\s+correspond|"
                           # "<claim> says X, but/whereas the <document> shows Y"
                           r"(?:\bbut\b|\bwhereas\b|\bwhile\b|\byet\b)[^.;]{0,80}\b(?:shows?|records?|states?|lists?|"
                           r"indicates?|reads?|confirms?)\b", re.I)
GAP = re.compile(r"\black(?:s|ing)?\b|missing|absen(?:t|ce)|\bno\s+[^.;]{0,60}?\b(?:provided|uploaded|attached|"
                 r"available|given|submitted|included|shared)\b|not\s+(?:yet\s+)?(?:provided|uploaded|attached|confirmed|verified|available|"
                 r"specified)|unverif|without|vague|minimal|insufficient|pending|awaiting|unconfirmed|requires?\b|"
                 r"incomplete|unclear|generic|no\s+(?:official|verified|formal|specific|detailed)", re.I)
EXPIRY_CLAIM = re.compile(r"\bexpired\b|\boutdated\b|\bstale\b|out\s+of\s+date|backdated", re.I)
_STOP = {"campaign", "document", "documents", "retrieved", "evidence", "record", "records", "requested", "request",
         "amount", "patient", "student", "beneficiary", "claim", "claims", "showing", "shows", "states", "pitch",
         "between", "provided", "official", "verified", "specific", "listed", "contains", "there", "which", "their",
         "about", "these", "those", "while", "where", "funds", "funding"}


class Concern(BaseModel):
    text: str
    type: str
    source: str                      # structured | text
    grounded: bool = False
    vetoed: bool = False             # set when a deterministic check refutes the concern
    veto_reason: Optional[str] = None
    document: Optional[str] = None
    evidence_quote: Optional[str] = None

    @property
    def escalates(self) -> bool:
        return self.type in ("FRAUD_INDICATOR", "CONTRADICTION") and self.grounded and not self.vetoed


def classify_text(text: str) -> str:
    if claims_future_date(text) or EXPIRY_CLAIM.search(text or ""):
        return "DATE_CLAIM"
    if FRAUD.search(text or ""):
        return "FRAUD_INDICATOR"
    if CONTRADICTION.search(text or ""):
        return "CONTRADICTION"
    if GAP.search(text or ""):
        return "INFORMATION_GAP"
    return "OTHER"


STRUCTURED_TYPES = {"SUSPECTED_FRAUD": "FRAUD_INDICATOR", "CONTRADICTION": "CONTRADICTION",
                    "MISSING_INFORMATION": "INFORMATION_GAP", "DATE_ISSUE": "DATE_CLAIM", "OTHER": "OTHER"}


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").casefold()))


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").casefold().replace(",", "")))


def quote_in_evidence(quote: str, evidence: str) -> bool:
    if not quote or len(quote.strip()) < SETTINGS["min_quote_chars"]:
        return False
    q, e = _norm(quote), _norm(evidence)
    if q and q in e:
        return True
    qt = _tokens(quote)
    return bool(qt) and len(qt & _tokens(evidence)) / len(qt) >= SETTINGS["quote_token_overlap"]


def text_grounded(concern: str, evidence: str, campaign_text: str, titles: Iterable[str]) -> bool:
    """A free-text concern is grounded if it names a retrieved document or cites a number / distinctive word that
    only the documents contain (so it cannot have come from the campaign's own claims)."""
    lowered = (concern or "").casefold()
    if any(t and t.casefold() in lowered for t in titles):
        return True
    evidence_tokens, campaign_tokens = _tokens(evidence), _tokens(campaign_text)
    for token in _tokens(concern):
        distinctive = (token.isdigit() and len(token) >= 2) or (token.isalpha() and len(token) >= 5 and token not in _STOP)
        if distinctive and token in evidence_tokens and token not in campaign_tokens:
            return True
    return False


def build_concerns(gemini: dict, evidence_chunks: List[dict], campaign_text: str,
                   dates: Optional[DateAssessment]) -> List[Concern]:
    evidence = "\n".join(c.get("text", "") for c in evidence_chunks)
    titles = [c.get("title", "") for c in evidence_chunks]
    concerns = []
    for item in gemini.get("concerns") or []:            # dated prompt: structured concerns
        kind = STRUCTURED_TYPES.get(str(item.get("category", "OTHER")).upper(), "OTHER")
        text = item.get("description", "")
        quote = item.get("evidence_quote") or ""
        concerns.append(Concern(text=text, type=kind, source="structured", document=item.get("document_title"),
                                evidence_quote=quote or None, grounded=quote_in_evidence(quote, evidence)))
    if not concerns:                                       # production schema: free-text red flags
        for text in gemini.get("red_flag_texts") or gemini.get("red_flags") or []:
            if not isinstance(text, str):
                continue
            kind = classify_text(text)
            concerns.append(Concern(text=text, type=kind, source="text",
                                    grounded=kind in ("FRAUD_INDICATOR", "CONTRADICTION")
                                    and text_grounded(text, evidence, campaign_text, titles)))
    if dates is not None:
        for concern in concerns:
            if concern.type == "DATE_CLAIM" and claims_future_date(concern.text) and not dates.future:
                concern.vetoed = True
                concern.veto_reason = (f"No document issue date is after the reference date "
                                       f"{dates.reference_date.isoformat()}.")
            elif concern.type == "DATE_CLAIM" and not claims_future_date(concern.text) and not dates.expired:
                concern.vetoed = True
                concern.veto_reason = "No document is expired or older than the maximum age."
    return concerns
