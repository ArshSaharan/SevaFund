"""Frozen settings for the development-only improved V3 + Gemini path (hybrid v2)."""
import hashlib
import json

POLICY_VERSION = "hybrid-v2-dev-1"

SETTINGS = {
    "date_grace_days": 1,            # a document dated up to this many days after the reference date is not "future"
    "max_document_age_days": 365,    # an issue date older than this makes the document expired (stale)
    "min_quote_chars": 12,           # a structured evidence quote shorter than this cannot ground a contradiction
    "quote_token_overlap": 0.8,      # fuzzy match threshold for a quote against retrieved evidence
}


def digest() -> str:
    return hashlib.sha256(json.dumps({"version": POLICY_VERSION, **SETTINGS}, sort_keys=True).encode()).hexdigest()[:16]
