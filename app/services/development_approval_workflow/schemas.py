"""Typed records for the development-only approval workflow.

The workflow sits *after* automated verification (frozen V3).  Automated
verification can at most make a campaign ELIGIBLE_PENDING_CONFIRMATION; only
recorded external confirmations can make it VERIFIED_ACTIVE, and only
VERIFIED_ACTIVE releases funds.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    ELIGIBLE_PENDING_CONFIRMATION = "ELIGIBLE_PENDING_CONFIRMATION"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    VERIFIED_ACTIVE = "VERIFIED_ACTIVE"
    REJECTED = "REJECTED"
    VERIFICATION_ERROR = "VERIFICATION_ERROR"


class ConfirmationCheck(str, Enum):
    BENEFICIARY = "BENEFICIARY"                  # the person, or the organisation's legal identity
    PAYMENT_DESTINATION = "PAYMENT_DESTINATION"  # payout account belongs to the institution or verified beneficiary
    INSTITUTION = "INSTITUTION"                  # hospital / educational institution / registering authority


class ContactSource(str, Enum):
    """Where the verifier obtained the contact details used for a confirmation."""
    OFFICIAL_REGISTRY = "OFFICIAL_REGISTRY"            # e.g. NGO Darpan, society registrar, NMC/state council
    OFFICIAL_DIRECTORY = "OFFICIAL_DIRECTORY"          # institution's published switchboard / website
    PLATFORM_KYC = "PLATFORM_KYC"                      # platform-run identity / bank-account verification
    PRIOR_VERIFIED_RECORD = "PRIOR_VERIFIED_RECORD"    # contact verified in an earlier, closed campaign
    CAMPAIGN_SUPPLIED = "CAMPAIGN_SUPPLIED"            # taken from the campaign or its uploads


INDEPENDENT_SOURCES = {ContactSource.OFFICIAL_REGISTRY, ContactSource.OFFICIAL_DIRECTORY,
                       ContactSource.PLATFORM_KYC, ContactSource.PRIOR_VERIFIED_RECORD}


class ConfirmationOutcome(str, Enum):
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"     # the independent party disputes a material fact
    UNREACHABLE = "UNREACHABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class ConfirmationRecord(BaseModel):
    check: ConfirmationCheck
    outcome: ConfirmationOutcome
    contact_source: ContactSource
    # Phone / e-mail / registry ID actually used.  Compared against the campaign's own
    # text: a contact that appears in the uploads is treated as campaign-supplied.
    contact_reference: str = ""
    verifier_id: str
    note: str = ""
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RequiredConfirmation(BaseModel):
    check: ConfirmationCheck
    description: str
    satisfied: bool = False
    satisfied_by: Optional[int] = None       # index into WorkflowRecord.confirmations


class Transition(BaseModel):
    from_state: Optional[WorkflowState]
    to_state: WorkflowState
    trigger: str                              # automated_verification | confirmation | reviewer | resubmission
    actor: str
    reason: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutomatedOutcome(BaseModel):
    """The minimum the workflow needs from automated verification.  Built from a
    live V3 result (`from_v3`) or from saved case-level predictions."""
    decision: str                             # V3 decision value
    category: str
    beneficiary_type: Optional[str] = "SELF"
    names_institution: bool = True            # medical/education campaigns name a hospital/institution
    reasons: List[str] = Field(default_factory=list)
    information_requests: List[str] = Field(default_factory=list)
    finding_codes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    engine_version: str = ""

    @classmethod
    def from_v3(cls, result, case) -> "AutomatedOutcome":
        return cls(decision=result.decision.value, category=case.category, beneficiary_type=case.beneficiary_type,
                   reasons=list(result.reasons), information_requests=list(result.information_requests),
                   finding_codes=sorted({f.code for f in result.findings}), errors=list(result.errors),
                   engine_version=result.engine_version)


class WorkflowRecord(BaseModel):
    state: WorkflowState
    automated: AutomatedOutcome
    required_confirmations: List[RequiredConfirmation] = Field(default_factory=list)
    confirmations: List[ConfirmationRecord] = Field(default_factory=list)
    information_requests: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    history: List[Transition] = Field(default_factory=list)

    @property
    def disbursement_allowed(self) -> bool:
        """Funds move only after every required external confirmation is complete."""
        return self.state == WorkflowState.VERIFIED_ACTIVE

    @property
    def is_fraud_detection(self) -> bool:
        """Pending confirmation is *not* a fraud detection; only review/rejection are."""
        return self.state in (WorkflowState.FLAG_FOR_REVIEW, WorkflowState.REJECTED)

    @property
    def pending_checks(self) -> List[ConfirmationCheck]:
        return [r.check for r in self.required_confirmations if not r.satisfied]
