"""Hybrid v3: safety-gated V3 + Gemini verification (development only).

Built on top of frozen V3 (app/services/development_verifier_v3) and frozen hybrid v2
(app/services/development_gemini_verification), neither of which is modified.  Nothing in production imports
this package; app/services/ai_verifier.py and the production default model are unchanged.
See docs/hybrid_v3_safety_changes.md.
"""
from .config import POLICY_VERSION, SETTINGS
from .confirmation import activation_status, start_record
from .crossdoc import GEMINI_DEPENDENT, CrossFinding
from .dates import DateAssessment, assess
from .financial import FinancialEvidence, assess_financial, is_financial
from .policy import HybridV3Decision, assess_case, combine, effective_v3, v3_case

__all__ = ["CrossFinding", "DateAssessment", "FinancialEvidence", "GEMINI_DEPENDENT", "HybridV3Decision", "POLICY_VERSION",
           "SETTINGS", "activation_status", "assess", "assess_case", "assess_financial", "combine", "effective_v3",
           "is_financial", "start_record", "v3_case"]
