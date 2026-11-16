"""Trace live Gemini failures on a small stratified synthetic diagnostic set."""
import asyncio
import csv
import json
import logging
import math
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import httpx
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services import rag
from app.services.ai_verifier import ai_verifier

DATASET = ROOT / "evaluation" / "fundraising_scenarios.jsonl"
REPORT = ROOT / "evaluation" / "gemini_diagnostic_results.json"
DETAILS = ROOT / "evaluation" / "gemini_diagnostic_cases.csv"
CASE_IDS = [
    "SYN-001", "SYN-006",  # legitimate medical
    "SYN-061", "SYN-062",  # fraudulent medical
    "SYN-121", "SYN-122",  # borderline medical
    "SYN-125", "SYN-126",  # borderline community / education
    "SYN-161", "SYN-163",  # legitimate education / community
    "SYN-181", "SYN-183",  # fraudulent education / community
]
LOCAL_MODEL = "crowdfund-india-trust-v1"


def classify_fallback(record):
    status = record.get("generation_http_status")
    exception_type = record.get("generation_exception_type")
    if status == 429:
        return "RATE_LIMIT_429"
    if status is not None and status >= 500:
        return "API_5XX"
    if status is not None and status >= 400:
        return "API_4XX"
    if exception_type in {"ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "TimeoutException"}:
        return "TIMEOUT"
    if exception_type == "JSONDecodeError":
        return "JSON_PARSE_ERROR"
    if exception_type == "ValidationError":
        return "PYDANTIC_SCHEMA_VALIDATION"
    if exception_type in {"KeyError", "IndexError", "TypeError", "ValueError"}:
        return "RESPONSE_SHAPE_OR_VALUE_ERROR"
    if exception_type:
        return f"OTHER_EXCEPTION:{exception_type}"
    if status == 200:
        return "HTTP_200_BUT_NO_VERIFICATION_RESULT"
    return "NO_GENERATION_RESPONSE_RECORDED"


async def preflight():
    endpoints = [
        ("generation", f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent", {
            "contents": [{"parts": [{"text": "Reply with the word ready."}]}],
            "generationConfig": {"temperature": 0},
        }),
        ("embedding", f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents", {
            "requests": [{
                "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                "content": {"parts": [{"text": "fundraising diagnostic preflight"}]},
                "taskType": "RETRIEVAL_DOCUMENT",
            }],
        }),
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        for name, url, payload in endpoints:
            response = await client.post(url, headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=payload)
            if response.status_code != 200:
                try:
                    error = response.json().get("error", {})
                    provider_status = error.get("status", "UNKNOWN")
                    provider_code = error.get("code", response.status_code)
                    reasons = [item.get("reason") for item in error.get("details", []) if item.get("reason")]
                except Exception:
                    provider_status, provider_code, reasons = "UNPARSEABLE_ERROR", response.status_code, []
                retry_hint = response.headers.get("Retry-After", "not provided")
                raise SystemExit(
                    f"Gemini {name} preflight stopped (HTTP {response.status_code}; provider status {provider_status}; "
                    f"provider code {provider_code}; reason {','.join(reasons) or 'not provided'}; retry-after {retry_hint}); no cases were sent."
                )


async def run_diagnostic(cases):
    records = []
    current = {"record": None}
    original_client = httpx.AsyncClient

    class TracingAsyncClient:
        def __init__(self, *args, **kwargs):
            self.inner = original_client(*args, **kwargs)

        async def __aenter__(self):
            await self.inner.__aenter__()
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return await self.inner.__aexit__(exc_type, exc, tb)

        async def post(self, url, *args, **kwargs):
            record = current["record"]
            stage = "generation" if ":generateContent" in url else "embedding" if "EmbedContents" in url or ":embedContent" in url else "other"
            try:
                response = await self.inner.post(url, *args, **kwargs)
                if record is not None:
                    record["api_events"].append({"stage": stage, "http_status": response.status_code})
                    if stage == "generation":
                        record["generation_http_status"] = response.status_code
                    if stage == "embedding" and response.status_code >= 400:
                        record["embedding_errors"].append(f"HTTP_{response.status_code}")
                return response
            except Exception as exc:
                if record is not None:
                    name = type(exc).__name__
                    record["api_events"].append({"stage": stage, "exception_type": name})
                    if stage == "generation":
                        record["generation_exception_type"] = name
                    if stage == "embedding":
                        record["embedding_errors"].append(name)
                raise

    original_verify = ai_verifier._verify_with_gemini

    async def traced_verify(**kwargs):
        record = current["record"]
        try:
            return await original_verify(**kwargs)
        except Exception as exc:
            if record is not None:
                record["generation_exception_type"] = type(exc).__name__
                # GeminiAPIError exposes only the sanitized classification.
                record["fallback_reason"] = getattr(exc, "category", None) or record.get("fallback_reason")
            raise

    httpx.AsyncClient = TracingAsyncClient
    ai_verifier._verify_with_gemini = traced_verify
    original_upload_dir = rag.UPLOAD_DIR
    scratch = tempfile.TemporaryDirectory(prefix="fundraising-gemini-diagnostic-")
    rag.UPLOAD_DIR = Path(scratch.name)
    try:
        for case in cases:
            record = {
                "case_id": case["case_id"],
                "ground_truth": case["ground_truth"],
                "category": case["input"]["category"],
                "scenario_group": case["scenario_group"],
                "api_events": [],
                "embedding_errors": [],
            }
            current["record"] = record
            docs = []
            for index, doc in enumerate(case["input"].get("documents", []), start=1):
                filename = f"{case['case_id'].lower()}-{index}.txt"
                (rag.UPLOAD_DIR / filename).write_text(doc["content"], encoding="utf-8")
                docs.append({
                    "doc_type": doc["doc_type"],
                    "title": doc["title"],
                    "file_url": f"/private-documents/{filename}",
                    "verified": False,
                })
            started = time.perf_counter()
            result = await ai_verifier.verify_campaign_request(
                title=case["input"]["title"],
                category=case["input"]["category"],
                story=case["input"]["story"],
                goal_amount=case["input"]["goal_amount"],
                beneficiary_name=case["input"].get("beneficiary_name"),
                beneficiary_type=case["input"].get("beneficiary_type", "SELF"),
                location=f"{case['input'].get('city', '')}, {case['input'].get('state', '')}".strip(", "),
                proof_documents=docs,
            )
            record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            record["model_used"] = result.model_used
            record["gemini_success"] = result.model_used != LOCAL_MODEL
            record["recommendation"] = result.recommendation
            if record["gemini_success"]:
                record["fallback_reason"] = None
            elif not record.get("fallback_reason"):
                record["fallback_reason"] = classify_fallback(record)
            # Keep only status codes and exception classes. No prompt, response body, URL, or credential is recorded.
            record["embedding_errors"] = sorted(set(record["embedding_errors"]))
            records.append(record)
    finally:
        httpx.AsyncClient = original_client
        ai_verifier._verify_with_gemini = original_verify
        rag.UPLOAD_DIR = original_upload_dir
        scratch.cleanup()
    return records


def main():
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is not configured; no cases were sent.")
    all_cases = {row["case_id"]: row for row in (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines())}
    cases = [all_cases[case_id] for case_id in CASE_IDS]
    if len(cases) != 12:
        raise SystemExit("The stratified diagnostic case list is incomplete")

    logging.getLogger("ai_verifier").disabled = True
    try:
        asyncio.run(preflight())
    except SystemExit as exc:
        blocked = {
            "dataset": DATASET.name,
            "diagnostic_case_count": len(cases),
            "cases_sent": 0,
            "status": "blocked_at_preflight",
            "preflight_error": str(exc),
            "models": {"generation": settings.GEMINI_MODEL, "embedding": settings.GEMINI_EMBEDDING_MODEL},
            "logging_policy": "No credentials, request bodies, response bodies, or provider messages are recorded.",
        }
        REPORT.write_text(json.dumps(blocked, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(blocked, indent=2))
        return
    records = asyncio.run(run_diagnostic(cases))

    by_category = {}
    by_truth_category = {}
    for category in sorted({r["category"] for r in records}):
        group = [r for r in records if r["category"] == category]
        by_category[category] = {
            "cases": len(group),
            "gemini_successes": sum(r["gemini_success"] for r in group),
            "success_rate": round(sum(r["gemini_success"] for r in group) / len(group), 4),
            "fallbacks": sum(not r["gemini_success"] for r in group),
        }
    for label in ("legitimate", "fraudulent", "borderline"):
        for category in sorted({r["category"] for r in records}):
            group = [r for r in records if r["ground_truth"] == label and r["category"] == category]
            if group:
                by_truth_category[f"{label}:{category}"] = {
                    "cases": len(group),
                    "gemini_successes": sum(r["gemini_success"] for r in group),
                    "success_rate": round(sum(r["gemini_success"] for r in group) / len(group), 4),
                }
    report = {
        "dataset": DATASET.name,
        "case_count": len(records),
        "synthetic": True,
        "models": {"generation": settings.GEMINI_MODEL, "embedding": settings.GEMINI_EMBEDDING_MODEL},
        "logging_policy": "Only case ids, labels, categories, HTTP status codes, exception classes, and timings are retained; credentials and request/response bodies are omitted.",
        "gemini_successes": sum(r["gemini_success"] for r in records),
        "fallbacks": sum(not r["gemini_success"] for r in records),
        "fallback_reason_counts": dict(Counter(r["fallback_reason"] for r in records if r["fallback_reason"])),
        "embedding_error_counts": dict(Counter(error for r in records for error in r["embedding_errors"])),
        "success_rate_by_category": by_category,
        "success_rate_by_truth_and_category": by_truth_category,
        "cases": records,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with DETAILS.open("w", newline="", encoding="utf-8") as handle:
        fields = ["case_id", "ground_truth", "category", "scenario_group", "model_used", "gemini_success", "fallback_reason", "generation_http_status", "generation_exception_type", "embedding_errors", "recommendation", "latency_ms"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field) for field in fields}
            row["embedding_errors"] = ";".join(record["embedding_errors"])
            writer.writerow(row)
    print(json.dumps({key: report[key] for key in (
        "case_count", "gemini_successes", "fallbacks", "fallback_reason_counts", "embedding_error_counts", "success_rate_by_category", "success_rate_by_truth_and_category"
    )}, indent=2))


if __name__ == "__main__":
    main()
