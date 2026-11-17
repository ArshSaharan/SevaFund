"""Hybrid v4: hybrid v3 plus independent amount confirmation, payment-account checks, an assisted route for
applicants without formal quotations, and a tamper-evident audit record (development only).

Built on frozen V3, frozen hybrid v2 and frozen hybrid v3, none of which is modified.  Nothing in production imports
this package; app/services/ai_verifier.py and the production default model are unchanged.
See docs/SEVAFUND_FINAL_REPORT.md.
"""
from .audit import AuditLog, case_fingerprint
from .config import POLICY_VERSION, REQUIRED_CHECKS, SETTINGS, digest
from .payment import PaymentFinding, check as check_payment_accounts
from .policy import Finding, HybridV4Decision, assess_case, decide
from .workflow import (ASSISTED_COST_CONFIRMATION, Check, Confirmation, IllegalTransition, Record, activation_status,
                       assisted_cost_review, record_confirmation, reviewer_resolution, start, suspend)

__all__ = ["ASSISTED_COST_CONFIRMATION", "AuditLog", "Check", "Confirmation", "Finding", "HybridV4Decision",
           "IllegalTransition", "POLICY_VERSION", "PaymentFinding", "REQUIRED_CHECKS", "Record", "SETTINGS",
           "activation_status", "assess_case", "assisted_cost_review", "case_fingerprint", "check_payment_accounts",
           "decide", "digest", "record_confirmation", "reviewer_resolution", "start", "suspend"]
