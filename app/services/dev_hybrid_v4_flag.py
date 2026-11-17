"""Development-only feature flag for the hybrid v4 integration.  OFF by default.

    SEVAFUND_DEV_HYBRID_V4=1                       enable (accepted: 1, true, yes, on)
    SEVAFUND_DEV_HYBRID_V4_GEMINI=<mode>           offline Gemini stand-in used by the integration:
        off (default)        Gemini is not run; hybrid v4 then never approves (VERIFICATION_ERROR)
        mock-approve         scripted AUTO_APPROVE answer
        mock-nmi             scripted information request about cost evidence
        mock-flag-unquoted   scripted unquoted fraud suspicion
        mock-fail            scripted server error
    There is no live mode: the integration never calls the Gemini API.

This module deliberately imports nothing else from the integration, so with the flag off the integration code, its
database table and its routes are never loaded or used, and production behaviour is unchanged.  The flag is read
from the environment on every call (not from app/config.py, which is production configuration).
"""
import os

FLAG = "SEVAFUND_DEV_HYBRID_V4"
GEMINI_MODE = "SEVAFUND_DEV_HYBRID_V4_GEMINI"
GEMINI_MODES = ("off", "mock-approve", "mock-nmi", "mock-flag-unquoted", "mock-fail")


def enabled() -> bool:
    return os.getenv(FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def gemini_mode() -> str:
    mode = os.getenv(GEMINI_MODE, "off").strip().lower()
    return mode if mode in GEMINI_MODES else "off"
