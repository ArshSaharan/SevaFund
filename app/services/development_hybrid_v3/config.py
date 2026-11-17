"""Settings for hybrid v3 (development only).  Nothing in production imports this package."""
import hashlib
import json

POLICY_VERSION = "hybrid-v3-dev-1"

SETTINGS = {
    "date_grace_days": 1,                 # an issue date up to 1 day after the reference date is tolerated
    "max_document_age_days": 365,         # time-sensitive documents (cost, fee, income, enrolment) older than this
    "date_conflict_tolerance_days": 2,    # same event recorded with dates further apart than this -> contradiction
    "age_conflict_tolerance_years": 1,
    "amount_support_tolerance": 0.05,     # goal may exceed the documented need by at most 5 %
    "amount_conflict_tolerance": 0.02,    # same-issuer outstanding amounts differing by more than 2 % ...
    "amount_conflict_min_inr": 1000,      # ... and by more than INR 1,000 -> contradiction
    "min_financial_traceability": 2,      # of: issuer, date, reference number, signatory
}


def digest() -> str:
    return hashlib.sha256(json.dumps({"policy": POLICY_VERSION, "settings": SETTINGS}, sort_keys=True).encode()).hexdigest()[:16]
