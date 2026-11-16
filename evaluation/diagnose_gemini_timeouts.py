"""Probe Gemini generation and embedding latency without sending evaluation cases."""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.gemini_api import _provider_category

CONNECT_TIMEOUT_S = 10
READ_TIMEOUT_S = 90
WRITE_TIMEOUT_S = 20
POOL_TIMEOUT_S = 10
MODEL = settings.GEMINI_MODEL
EMBEDDING_MODEL = settings.GEMINI_EMBEDDING_MODEL


def error_record(stage, exc, elapsed_s):
    return {
        "stage": stage,
        "success": False,
        "latency_seconds": round(elapsed_s, 3),
        "exception_type": type(exc).__name__,
        "failure_phase": (
            "connect" if isinstance(exc, httpx.ConnectTimeout) else
            "read" if isinstance(exc, httpx.ReadTimeout) else
            "write" if isinstance(exc, httpx.WriteTimeout) else
            "pool" if isinstance(exc, httpx.PoolTimeout) else
            "timeout_phase_unknown" if isinstance(exc, httpx.TimeoutException) else
            "network"
        ),
    }


async def probe(stage, url, payload):
    timeout = httpx.Timeout(
        connect=CONNECT_TIMEOUT_S,
        read=READ_TIMEOUT_S,
        write=WRITE_TIMEOUT_S,
        pool=POOL_TIMEOUT_S,
    )
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json=payload,
            )
        elapsed = time.perf_counter() - started
        record = {"stage": stage, "success": response.status_code == 200, "latency_seconds": round(elapsed, 3), "http_status": response.status_code}
        if response.status_code != 200:
            try:
                body = response.json()
            except ValueError:
                body = {}
            error = body.get("error", {}) if isinstance(body, dict) else {}
            if not isinstance(error, dict):
                error = {}
            record.update({
                "provider_status": error.get("status"),
                "provider_code": error.get("code"),
                "sanitized_category": _provider_category(response.status_code, body),
            })
        else:
            try:
                data = response.json()
            except ValueError:
                data = {}
            candidates = data.get("candidates", []) if isinstance(data, dict) else []
            record["finish_reason"] = candidates[0].get("finishReason") if candidates else None
            record["response_has_text"] = bool(candidates and candidates[0].get("content", {}).get("parts"))
        return record
    except httpx.TimeoutException as exc:
        return error_record(stage, exc, time.perf_counter() - started)
    except httpx.RequestError as exc:
        return error_record(stage, exc, time.perf_counter() - started)


async def main():
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is not configured; no requests were sent")

    generation_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    embedding_url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:batchEmbedContents"
    base_generation = {
        "contents": [{"parts": [{"text": "Reply with exactly: READY"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
    }
    low_thinking_generation = {
        "contents": [{"parts": [{"text": "Reply with exactly: READY"}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 256,
            "thinkingConfig": {"thinkingLevel": "LOW"},
        },
    }
    embedding_payload = {
        "requests": [{
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": "fundraising evidence retrieval diagnostic"}]},
            "taskType": "RETRIEVAL_QUERY",
        }],
    }
    results = [
        await probe("generation_default_thinking", generation_url, base_generation),
        await probe("generation_low_thinking", generation_url, low_thinking_generation),
        await probe("embedding", embedding_url, embedding_payload),
    ]
    return {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": 0,
        "evaluation_started": False,
        "models": {"generation": MODEL, "embedding": EMBEDDING_MODEL},
        "httpx_timeouts_seconds": {
            "connect": CONNECT_TIMEOUT_S,
            "read": READ_TIMEOUT_S,
            "write": WRITE_TIMEOUT_S,
            "pool": POOL_TIMEOUT_S,
            "overall_deadline": None,
        },
        "probes": results,
        "both_endpoints_passed": all(item["success"] for item in results),
        "logging_policy": "No API key, request headers, prompt/response text, or raw provider body recorded.",
    }


if __name__ == "__main__":
    report = asyncio.run(main())
    run_id = datetime.now(timezone.utc).strftime("gemini_timeout_diagnostic_%Y%m%dT%H%M%SZ")
    out_dir = Path(__file__).with_name("runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    report_path = out_dir / "results.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "results_path": str(report_path)}, indent=2))
