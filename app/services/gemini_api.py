"""Small Gemini REST client with bounded retries and credential-safe errors."""
import asyncio
import time
from typing import Any, Dict, Optional, Union

import httpx


class GeminiAPIError(Exception):
    def __init__(
        self,
        stage: str,
        category: str,
        status_code: Optional[int] = None,
        exception_type: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ):
        self.stage = stage
        self.category = category
        self.status_code = status_code
        self.exception_type = exception_type
        self.duration_seconds = duration_seconds
        super().__init__(f"{stage}:{category}")


def _provider_category(status_code: int, body: Any) -> str:
    error = body.get("error", {}) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    code = str(error.get("status", "")).upper()
    details = error.get("details", [])
    details = details if isinstance(details, list) else []
    # Quota identifiers live in QuotaFailure.violations[], e.g.
    # "GenerateRequestsPerDayPerProjectPerModel-FreeTier".
    entries = [d for d in details if isinstance(d, dict)]
    for detail in list(entries):
        violations = detail.get("violations", [])
        if isinstance(violations, list):
            entries.extend(v for v in violations if isinstance(v, dict))
    reasons = " ".join(
        str(entry.get(key, ""))
        for entry in entries
        for key in ("reason", "quotaId", "quota_id")
    ).upper()
    if status_code == 429:
        if any(token in reasons for token in ("PERDAY", "PER_DAY", "DAILY", "RPD")) or "QUOTA_EXCEEDED" in code:
            return "QUOTA_EXHAUSTED"
        if "RATE_LIMIT" in reasons or "TOO_MANY_REQUESTS" in code:
            return "RATE_LIMIT"
        return "RESOURCE_EXHAUSTED"
    if status_code in (401, 403):
        return "AUTHENTICATION" if status_code == 401 else "PERMISSION_DENIED"
    if status_code == 404:
        return "MODEL_NOT_FOUND"
    if status_code == 400:
        return "BAD_REQUEST"
    if status_code == 408:
        return "TIMEOUT"
    if status_code >= 500:
        return "SERVER_ERROR"
    return "HTTP_ERROR"


def _retry_delay(response: httpx.Response, retry_index: int) -> float:
    value = response.headers.get("Retry-After")
    if value:
        try:
            return max(0.0, min(10.0, float(value)))
        except ValueError:
            pass
    return min(4.0, 0.75 * (2 ** retry_index))


async def post_json(
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    stage: str,
    timeout_seconds: Union[float, httpx.Timeout],
    max_attempts: int = 2,
) -> Dict[str, Any]:
    """POST JSON without placing the API key in the URL or exception text."""
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    started = time.perf_counter()
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            category = {
                httpx.ConnectTimeout: "CONNECT_TIMEOUT",
                httpx.ReadTimeout: "READ_TIMEOUT",
                httpx.WriteTimeout: "WRITE_TIMEOUT",
                httpx.PoolTimeout: "POOL_TIMEOUT",
            }.get(type(exc), "TIMEOUT")
            raise GeminiAPIError(
                stage, category, exception_type=type(exc).__name__,
                duration_seconds=round(time.perf_counter() - started, 3),
            ) from exc
        except httpx.RequestError as exc:
            if attempt + 1 < max_attempts:
                await asyncio.sleep(min(4.0, 0.75 * (2 ** attempt)))
                continue
            raise GeminiAPIError(
                stage, "NETWORK_ERROR", exception_type=type(exc).__name__,
                duration_seconds=round(time.perf_counter() - started, 3),
            ) from exc

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as exc:
                raise GeminiAPIError(stage, "INVALID_API_JSON", 200) from exc
            if not isinstance(data, dict):
                raise GeminiAPIError(stage, "INVALID_API_RESPONSE", 200)
            return data

        category = _provider_category(response.status_code, _safe_json(response))
        # A daily quota exhaustion cannot recover from a short retry delay.
        retryable = response.status_code in (408, 429, 500, 502, 503, 504) and category != "QUOTA_EXHAUSTED"
        if retryable and attempt + 1 < max_attempts:
            await asyncio.sleep(_retry_delay(response, attempt))
            continue
        raise GeminiAPIError(
            stage, category, response.status_code,
            duration_seconds=round(time.perf_counter() - started, 3),
        )
    raise GeminiAPIError(stage, "RETRY_EXHAUSTED")


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {}
