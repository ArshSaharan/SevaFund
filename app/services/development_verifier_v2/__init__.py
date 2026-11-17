"""SevaFund development-only verifier, version 2.

Isolated from production: nothing in ``app/routers`` or ``app/services/ai_verifier``
imports this package.  See ``docs/development_verifier_v2.md``.
"""
from .config import DEFAULT_CONFIG, ENGINE_VERSION, VerifierConfig
from .engine import load_documents, verify_case
from .schemas import CaseInput, Decision, DocumentInput, VerificationDecision

__all__ = ["CaseInput", "Decision", "DocumentInput", "VerificationDecision", "VerifierConfig",
           "DEFAULT_CONFIG", "ENGINE_VERSION", "load_documents", "verify_case"]
