"""Frozen configuration for the development-only v3 candidate.

Every threshold that affects a decision lives here so that a run can be
reproduced from (code hash, config digest, dataset hash).
"""
import hashlib
import json

from pydantic import BaseModel, Field

ENGINE_VERSION = "sevafund-development-candidate-v3.0"


class VerifierConfig(BaseModel):
    # Component switches (used by the ablation study).
    enable_cross_document: bool = True
    enable_category: bool = True
    enable_semantic: bool = True
    enable_financial_parsing: bool = True
    enable_evidence_tiers: bool = True
    enable_uncertainty_policy: bool = True
    # Decision policy.
    flag_confidence: float = 0.6        # a material finding at/above this routes to human review
    reject_confidence: float = 0.8      # rejection needs >=2 independent findings at/above this
    # Amount reconciliation.
    amount_tolerance: float = 0.10      # requested may exceed documented need by this fraction
    amount_material_ratio: float = 1.5  # requested/documented at/above this is a material excess
    # Chronology.
    future_grace_days: int = 1
    lapsed_deadline_days: int = 120
    stale_document_days: int = 540
    # Evidence sufficiency.
    min_traceability: int = 2           # of: issuer, date, reference number, signatory
    verified_fx_rates: dict = Field(default_factory=dict)  # intentionally empty; no implicit FX conversion

    def digest(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


DEFAULT_CONFIG = VerifierConfig()
