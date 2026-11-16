"""Typed contracts shared by every stage of the development-only v2 verifier."""
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field as PydanticField


class Decision(str, Enum):
    APPROVED = "APPROVED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    REJECTED = "REJECTED"
    VERIFICATION_ERROR = "VERIFICATION_ERROR"


class Severity(str, Enum):
    MATERIAL = "material"      # a contradiction that, if real, undermines the claim
    UNCERTAIN = "uncertain"    # cannot be resolved from the dossier; ask, do not accuse


class DocumentInput(BaseModel):
    title: str = "Supporting document"
    doc_type: str = "OTHER"
    text: Optional[str] = None
    file_url: Optional[str] = None
    # Set by the loader when retrieval/extraction failed for a *system* reason.
    # Holds a sanitized category only, never file contents or provider messages.
    load_error: Optional[str] = None


class CaseInput(BaseModel):
    title: str
    category: str
    story: str
    goal_amount: float
    beneficiary_name: Optional[str] = None
    beneficiary_type: Optional[str] = "SELF"
    city: Optional[str] = None
    state: Optional[str] = None
    submitted_on: Optional[date] = None
    documents: List[DocumentInput] = PydanticField(default_factory=list)


class SourceRef(BaseModel):
    document: str
    doc_index: int = -1            # -1 denotes the campaign text itself
    page: Optional[int] = None
    chunk: Optional[int] = None    # same numbering as app.services.rag.chunk_document
    excerpt: str = ""


class ExtractedField(BaseModel):
    kind: str                      # person | organisation | date | amount | identifier | service
    role: str
    raw: str
    value: Any = None              # normalized: str, float (INR) or ISO date string
    confidence: float = 0.8
    source: SourceRef


class DocumentEvidence(BaseModel):
    index: int
    title: str
    doc_type: str
    readable: bool = True
    issuer: Optional[str] = None
    issuer_kind: Optional[str] = None
    evidence_classes: List[str] = PydanticField(default_factory=list)
    traceability: int = 0          # issuer + date + reference + signatory (0-4)
    fields: List[ExtractedField] = PydanticField(default_factory=list)
    issues: List[str] = PydanticField(default_factory=list)

    def of(self, kind: str, *roles: str) -> List[ExtractedField]:
        return [f for f in self.fields if f.kind == kind and (not roles or f.role in roles)]


class FindingValue(BaseModel):
    field: str
    value: str
    document: str
    doc_index: int = -1            # -1 = campaign text; otherwise position of the upload
    page: Optional[int] = None
    chunk: Optional[int] = None


class Finding(BaseModel):
    kind: str                      # identity, identifier, amount, settlement, institution, chronology, ...
    code: str = ""                 # stable machine-readable reason code
    dimension: str                 # scoring dimension the finding feeds
    component: str                 # cross_document | category | semantic | llm
    severity: Severity
    confidence: float              # 0-1: how sure the engine is that the conflict is real
    summary: str
    explanation: str               # why the inconsistency matters
    values: List[FindingValue] = PydanticField(default_factory=list)


class Requirement(BaseModel):
    key: str
    description: str
    satisfied: bool
    satisfied_by: List[str] = PydanticField(default_factory=list)
    request: str = ""              # what to ask the campaigner for when unsatisfied


class AuditRecord(BaseModel):
    """Privacy-preserving trace of one decision.  Contains no names, raw
    identifiers, document text or credentials - only redacted values."""
    case_fingerprint: str
    engine_version: str
    config_digest: str
    category: str
    document_count: int
    stages: List[Dict[str, Any]] = PydanticField(default_factory=list)
    decision: str = ""
    reason_codes: List[str] = PydanticField(default_factory=list)
    influencing_dimensions: List[str] = PydanticField(default_factory=list)
    findings: List[Dict[str, Any]] = PydanticField(default_factory=list)
    errors: List[str] = PydanticField(default_factory=list)


class VerificationDecision(BaseModel):
    decision: Decision
    risk_level: str
    authenticity_score: float                       # 0-100, higher = fewer concerns
    dimension_scores: Dict[str, float] = PydanticField(default_factory=dict)
    influencing_dimensions: List[str] = PydanticField(default_factory=list)
    reasons: List[str] = PydanticField(default_factory=list)
    findings: List[Finding] = PydanticField(default_factory=list)
    requirements: List[Requirement] = PydanticField(default_factory=list)
    information_requests: List[str] = PydanticField(default_factory=list)
    positive_signals: List[str] = PydanticField(default_factory=list)
    # Agreement between uploaded documents is not proof of authenticity.
    independent_verification: str = "UNAVAILABLE"
    uncertainty_notes: List[str] = PydanticField(default_factory=list)
    errors: List[str] = PydanticField(default_factory=list)
    evidence: List[DocumentEvidence] = PydanticField(default_factory=list)
    engine_version: str = ""
    audit: Optional[AuditRecord] = None

    @property
    def is_fraud_flag(self) -> bool:
        return self.decision in (Decision.FLAG_FOR_REVIEW, Decision.REJECTED)
