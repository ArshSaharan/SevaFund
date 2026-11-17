"""Safe Gemini call for the development path.  Never raises; every failure becomes a FAILED outcome.

By default it uses the production client `app.services.gemini_api.post_json` with its existing protections
(bounded retries with backoff, Retry-After handling, daily-quota detection, credential-safe errors).  An
evaluation may pass its own budgeted transport (one HTTP request per call, no hidden retries).
"""
import json
import time
from datetime import date
from typing import Awaitable, Callable, List, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.schemas.ai import VerificationResult
from app.services.gemini_api import GeminiAPIError

from .prompt import DATED_SCHEMA, build_prompt

Transport = Callable[..., Awaitable[dict]]
GENERATION_TIMEOUT = httpx.Timeout(connect=10, read=180, write=20, pool=10)   # same limits as production


class GeminiOutcome(BaseModel):
    status: str                                   # OK | FAILED
    failure_category: Optional[str] = None        # sanitized; never provider text or request content
    decision: Optional[str] = None                # APPROVED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | REJECTED
    risk_level: Optional[str] = None
    summary: Optional[str] = None
    red_flag_texts: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    concerns: List[dict] = Field(default_factory=list)
    latency_seconds: Optional[float] = None
    model: Optional[str] = None


_LEGACY = {"AUTO_APPROVE": "APPROVED", "NEEDS_MORE_INFO": "NEEDS_MORE_INFORMATION", "REJECT": "REJECTED",
           "FLAG_FOR_REVIEW": "FLAG_FOR_REVIEW"}


async def verify_with_gemini(case: dict, evidence_chunks: List[dict], reference_date: date,
                             submitted_on: Optional[date] = None, transport: Optional[Transport] = None,
                             api_key: Optional[str] = None, model: Optional[str] = None,
                             max_attempts: int = 2) -> GeminiOutcome:
    started = time.perf_counter()
    model = model or settings.GEMINI_MODEL
    key = settings.GEMINI_API_KEY if api_key is None else api_key

    def failed(category: str) -> GeminiOutcome:
        return GeminiOutcome(status="FAILED", failure_category=category, model=model,
                             latency_seconds=round(time.perf_counter() - started, 3))

    if not key:
        return failed("NOT_CONFIGURED")
    if transport is None:
        from app.services.gemini_api import post_json as transport
    payload = {"contents": [{"parts": [{"text": build_prompt(case, evidence_chunks, reference_date, submitted_on)}]}],
               "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json",
                                    "responseSchema": DATED_SCHEMA, "maxOutputTokens": 2048}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        data = await transport(url, key, payload, "generation", GENERATION_TIMEOUT, max_attempts=max_attempts)
        candidates = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(candidates, list) or not candidates:
            return failed("EMPTY_CANDIDATES")
        candidate = candidates[0]
        if candidate.get("finishReason") == "MAX_TOKENS":
            return failed("TRUNCATED_RESPONSE")
        if candidate.get("finishReason") in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
            return failed("MODEL_BLOCKED")
        text = "\n".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if isinstance(p, dict))
        if not text.strip():
            return failed("EMPTY_MODEL_TEXT")
        parsed = json.loads(text)
        validated = VerificationResult.model_validate(parsed)
        concerns = [c for c in parsed.get("concerns") or [] if isinstance(c, dict)]
        decision = _LEGACY.get(validated.recommendation)
        if decision is None:
            return failed("UNKNOWN_RECOMMENDATION")
        return GeminiOutcome(status="OK", decision=decision, risk_level=validated.risk_level, summary=validated.summary,
                             red_flag_texts=list(validated.red_flags), missing_requirements=list(validated.missing_requirements),
                             concerns=concerns, model=model, latency_seconds=round(time.perf_counter() - started, 3))
    except GeminiAPIError as exc:
        return failed(exc.category)
    except json.JSONDecodeError:
        return failed("JSON_PARSE_ERROR")
    except ValidationError:
        return failed("SCHEMA_VALIDATION")
    except Exception as exc:                       # noqa: BLE001 - a failure must never become an approval
        return failed(f"UNEXPECTED_{type(exc).__name__}")
