"""Development-only improved V3 + Gemini verification (hybrid v2).

Nothing in production imports this package; app/services/ai_verifier.py and the production default model are
unchanged.  See docs/hybrid_v2_development_report.md.
"""
from .client import GeminiOutcome, verify_with_gemini
from .concerns import Concern, build_concerns, classify_text
from .config import POLICY_VERSION
from .dates import DateAssessment, assess_dates
from .policy import CombinedDecision, combine

__all__ = ["CombinedDecision", "Concern", "DateAssessment", "GeminiOutcome", "POLICY_VERSION", "assess_dates",
           "build_concerns", "classify_text", "combine", "verify_with_gemini"]
