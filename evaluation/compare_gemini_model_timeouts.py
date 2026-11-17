"""One-shot, no-retry latency comparison for Gemini 3.8 Flash and 3.6 Flash."""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings

MODELS = ("gemini-3.8-flash", "gemini-3.6-flash")
TIMEOUT = httpx.Timeout(connect=10, read=180, write=20, pool=10)


def timeout_phase(exc):
    if isinstance(exc, httpx.ConnectTimeout):
        return "connect"
    if isinstance(exc, httpx.ReadTimeout):
        return "read"
    if isinstance(exc, httpx.WriteTimeout):
        return "write"
    if isinstance(exc, httpx.PoolTimeout):
        return "pool"
    if isinstance(exc, httpx.TimeoutException):
        return "unknown_timeout_phase"
    return "network"


async def model_catalog_check(client):
    started = time.perf_counter()
    try:
        response = await client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        )
    except httpx.RequestError as exc:
        return {"success": False, "latency_seconds": round(time.perf_counter() - started, 3), "exception_type": type(exc).__name__}
    record = {"success": response.status_code == 200, "http_status": response.status_code, "latency_seconds": round(time.perf_counter() - started, 3)}
    if response.status_code == 200:
        try:
            entries = response.json().get("models", [])
        except (ValueError, AttributeError):
            entries = []
        supported = {
            item.get("name", "").removeprefix("models/")
            for item in entries
            if isinstance(item, dict) and "generateContent" in item.get("supportedGenerationMethods", [])
        }
        record["models_available"] = {model: model in supported for model in MODELS}
    return record


async def generation_probe(client, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": "Reply with exactly: READY"}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 256,
            "thinkingConfig": {"thinkingLevel": "LOW"},
        },
    }
    started = time.perf_counter()
    try:
        response = await client.post(
            url,
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json=payload,
        )
    except httpx.RequestError as exc:
        return {
            "model": model,
            "success": False,
            "latency_seconds": round(time.perf_counter() - started, 3),
            "exception_type": type(exc).__name__,
            "failure_phase": timeout_phase(exc),
        }

    elapsed = round(time.perf_counter() - started, 3)
    record = {"model": model, "success": response.status_code == 200, "http_status": response.status_code, "latency_seconds": elapsed}
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 200:
        candidates = body.get("candidates", []) if isinstance(body, dict) else []
        candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        record["finish_reason"] = candidate.get("finishReason")
        record["response_valid"] = record["finish_reason"] == "STOP" and text.strip() == "READY"
    else:
        error = body.get("error", {}) if isinstance(body, dict) else {}
        record["provider_status"] = error.get("status") if isinstance(error, dict) else None
        record["provider_code"] = error.get("code") if isinstance(error, dict) else None
        record["quota_denied"] = response.status_code == 429
    return record


async def main():
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is not configured; no requests were sent")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        catalog = await model_catalog_check(client)
        if not catalog["success"]:
            return {
                "status": "blocked_at_catalog_check",
                "case_count": 0,
                "catalog": catalog,
                "probes": [],
                "automatic_retries": 0,
            }
        available = catalog.get("models_available", {})
        probes = []
        for model in MODELS:
            if not available.get(model, False):
                probes.append({"model": model, "success": False, "skipped": True, "reason": "not_listed_for_generateContent"})
                continue
            probes.append(await generation_probe(client, model))
        return {
            "status": "complete",
            "case_count": 0,
            "models": list(MODELS),
            "thinking_level": "LOW",
            "max_output_tokens": 256,
            "httpx_timeouts_seconds": {"connect": 10, "read": 180, "write": 20, "pool": 10},
            "automatic_retries": 0,
            "quota_note": "Gemini rate limits are visible in AI Studio; a catalog listing does not expose remaining quota. Each one-shot generation response records quota or availability errors returned by the API.",
            "catalog": catalog,
            "probes": probes,
            "logging_policy": "No API key, raw request/response text, or raw provider body is recorded.",
        }


if __name__ == "__main__":
    report = asyncio.run(main())
    run_id = datetime.now(timezone.utc).strftime("gemini_model_timeout_comparison_%Y%m%dT%H%M%SZ")
    out_dir = Path(__file__).with_name("runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    report_path = out_dir / "results.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "results_path": str(report_path)}, indent=2))
