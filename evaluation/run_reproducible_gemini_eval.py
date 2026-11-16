"""Sequential, resumable 200-case Gemini/RAG ablation evaluation.

Production model settings and fraud scoring are not modified. Successful model
outputs and document embeddings are cached in a per-run SQLite checkpoint.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import statistics
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path(__file__).with_name("fundraising_scenarios.jsonl")
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services import rag
from app.services.ai_verifier import ai_verifier
from app.services.fraud_detector import format_inr
from app.services.gemini_api import GeminiAPIError, _provider_category

PROMPT_VERSION = "ai-verifier-structured-rag-v2"
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 120.0
CONNECT_TIMEOUT_SECONDS = 10.0
READ_TIMEOUT_SECONDS = 90.0
WRITE_TIMEOUT_SECONDS = 20.0
POOL_TIMEOUT_SECONDS = 10.0
LOCAL_MODEL = "crowdfund-india-trust-v1"


class EvaluationRequestError(Exception):
    def __init__(self, stage, category, status_code=None, safe_details=None, duration_seconds=None, retryable=False, stop_run=False, retry_after_seconds=None):
        self.stage = stage
        self.category = category
        self.status_code = status_code
        self.safe_details = safe_details or {}
        self.duration_seconds = duration_seconds
        self.retryable = retryable
        self.stop_run = stop_run
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"{stage}:{category}")

    def as_dict(self):
        return {
            "stage": self.stage,
            "category": self.category,
            "http_status": self.status_code,
            "details": self.safe_details,
            "duration_seconds": self.duration_seconds,
            "retryable": self.retryable,
            "retry_after_seconds": self.retry_after_seconds,
        }


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(value=None):
    return (value or utc_now()).isoformat()


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def next_daily_reset_utc():
    pacific = ZoneInfo("America/Los_Angeles")
    now = utc_now().astimezone(pacific)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return next_midnight.astimezone(timezone.utc)


def _retry_after_seconds(response, message):
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(header) - utc_now()).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    match = re.search(r"retry(?:\s+in)?\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)", message or "", re.I)
    return float(match.group(1)) if match else None


def _quota_details(body, response):
    error = body.get("error", {}) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    violations = []
    details = error.get("details", [])
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            for violation in detail.get("violations", []) if isinstance(detail.get("violations", []), list) else []:
                if not isinstance(violation, dict):
                    continue
                dimensions = violation.get("quotaDimensions", {})
                if not isinstance(dimensions, dict):
                    dimensions = {}
                violations.append({
                    "quota_metric": violation.get("quotaMetric"),
                    "quota_id": violation.get("quotaId"),
                    "quota_value": violation.get("quotaValue"),
                    "dimensions": {key: dimensions[key] for key in ("model", "location") if key in dimensions},
                })
            reason = detail.get("reason")
            if reason:
                violations.append({"reason": str(reason)[:100]})
    all_quota_text = " ".join(
        f"{item.get('quota_id', '')} {item.get('quota_metric', '')} {item.get('reason', '')}"
        for item in violations
    ).upper()
    if any(token in all_quota_text for token in ("PERDAY", "PER_DAY", "DAILY", "REQUESTSPERDAY")):
        quota_kind = "daily"
    elif any(token in all_quota_text for token in ("PERMINUTE", "PER_MINUTE", "PERSECOND", "PER_SECOND")):
        quota_kind = "rate"
    else:
        quota_kind = "unknown"
    message = error.get("message", "")
    return {
        "provider_status": error.get("status"),
        "provider_code": error.get("code", response.status_code),
        "quota_violations": violations,
        "quota_kind": quota_kind,
        "retry_after_header": response.headers.get("Retry-After"),
        "retry_after_seconds": _retry_after_seconds(response, message),
    }, message


def _timeout_category(exc):
    if isinstance(exc, httpx.ConnectTimeout):
        return "CONNECT_TIMEOUT"
    if isinstance(exc, httpx.ReadTimeout):
        return "READ_TIMEOUT"
    if isinstance(exc, httpx.WriteTimeout):
        return "WRITE_TIMEOUT"
    if isinstance(exc, httpx.PoolTimeout):
        return "POOL_TIMEOUT"
    if isinstance(exc, httpx.TimeoutException):
        return "TIMEOUT"
    return "NETWORK_ERROR"


def _record_api_event(db, stage, outcome, attempt, status_code, category, duration, details):
    db.execute(
        "INSERT INTO api_events(at_utc, stage, case_id, outcome, attempt, http_status, category, duration_seconds, details_json) VALUES(?,?,?,?,?,?,?,?,?)",
        (iso_utc(), stage, getattr(db, "current_case_id", None), outcome, attempt, status_code, category, duration, json.dumps(details or {}, separators=(",", ":"))),
    )
    db.commit()


async def request_json(url, api_key, payload, stage, db, max_attempts=MAX_ATTEMPTS):
    phase_timeout = httpx.Timeout(
        connect=CONNECT_TIMEOUT_SECONDS,
        read=READ_TIMEOUT_SECONDS,
        write=WRITE_TIMEOUT_SECONDS,
        pool=POOL_TIMEOUT_SECONDS,
    )
    started = time.perf_counter()
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=phase_timeout) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                    json=payload,
                )
        except httpx.RequestError as exc:
            elapsed = round(time.perf_counter() - started, 3)
            category = _timeout_category(exc)
            retryable = attempt < max_attempts
            event = {"exception_type": type(exc).__name__}
            _record_api_event(db, stage, "exception", attempt, None, category, elapsed, event)
            if retryable:
                await asyncio.sleep(min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))))
                continue
            raise EvaluationRequestError(stage, category, safe_details=event, duration_seconds=elapsed, retryable=True, retry_after_seconds=BACKOFF_MAX_SECONDS) from None

        elapsed = round(time.perf_counter() - started, 3)
        if response.status_code == 200:
            try:
                body = response.json()
            except ValueError:
                body = None
            if not isinstance(body, dict):
                _record_api_event(db, stage, "invalid_json", attempt, 200, "INVALID_API_JSON", elapsed, {})
                raise EvaluationRequestError(stage, "INVALID_API_JSON", 200, duration_seconds=elapsed)
            _record_api_event(db, stage, "success", attempt, 200, None, elapsed, {})
            return body

        try:
            body = response.json()
        except ValueError:
            body = {}
        safe, message = _quota_details(body, response)
        category = _provider_category(response.status_code, body)
        is_daily = response.status_code == 429 and safe["quota_kind"] == "daily"
        retryable_status = response.status_code in (408, 429, 500, 502, 503, 504)
        retry_after = safe.get("retry_after_seconds")
        safe["exception_type"] = "HTTPStatusError"
        safe["attempt"] = attempt
        _record_api_event(db, stage, "http_error", attempt, response.status_code, category, elapsed, safe)

        if is_daily:
            safe["resume_after_utc"] = iso_utc(next_daily_reset_utc())
            raise EvaluationRequestError(
                stage, "DAILY_QUOTA_EXHAUSTED", response.status_code, safe, elapsed,
                retryable=True, stop_run=True, retry_after_seconds=None,
            )
        if not retryable_status or attempt >= max_attempts:
            raise EvaluationRequestError(
                stage, category, response.status_code, safe, elapsed,
                retryable=retryable_status, retry_after_seconds=retry_after,
            )

        exponential = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        delay = max(exponential, retry_after or 0.0)
        if delay > BACKOFF_MAX_SECONDS:
            safe["backoff_deferred_seconds"] = delay
            raise EvaluationRequestError(stage, category, response.status_code, safe, elapsed, retryable=True, retry_after_seconds=delay)
        await asyncio.sleep(delay)
    raise EvaluationRequestError(stage, "RETRY_EXHAUSTED", retryable=True)


def _api_wrapper(db, run_state):
    async def post_json(url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        try:
            return await request_json(url, api_key, payload, stage, db)
        except EvaluationRequestError as exc:
            if exc.stop_run:
                run_state["stop_reason"] = exc.as_dict()
            error = GeminiAPIError(
                stage, exc.category, exc.status_code,
                exception_type=exc.safe_details.get("exception_type"),
                duration_seconds=exc.duration_seconds,
            )
            error.safe_details = exc.safe_details
            error.stop_run = exc.stop_run
            error.retryable = exc.retryable
            error.retry_after_seconds = exc.retry_after_seconds
            raise error from None
    return post_json


def _init_db(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS predictions (
            config TEXT NOT NULL, case_id TEXT NOT NULL, status TEXT NOT NULL,
            payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(config, case_id)
        );
        CREATE TABLE IF NOT EXISTS embeddings (
            cache_key TEXT PRIMARY KEY, values_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at_utc TEXT NOT NULL, stage TEXT,
            case_id TEXT, outcome TEXT, attempt INTEGER, http_status INTEGER,
            category TEXT, duration_seconds REAL, details_json TEXT
        );
    """)
    connection.commit()
    # sqlite3.Connection instances do not accept arbitrary attributes. Keep
    # case attribution alongside the connection for safe API event logging.
    class EvaluationStore:
        def __init__(self, conn):
            self.connection = conn
            self.current_case_id = None

        def execute(self, *args, **kwargs):
            return self.connection.execute(*args, **kwargs)

        def executescript(self, *args, **kwargs):
            return self.connection.executescript(*args, **kwargs)

        def commit(self):
            return self.connection.commit()

        def close(self):
            return self.connection.close()

    return EvaluationStore(connection)


def _save_prediction(db, config, case_id, status, payload):
    db.execute(
        "INSERT INTO predictions(config,case_id,status,payload_json,updated_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(config,case_id) DO UPDATE SET status=excluded.status,payload_json=excluded.payload_json,updated_at=excluded.updated_at",
        (config, case_id, status, json.dumps(payload, ensure_ascii=False), iso_utc()),
    )
    db.commit()


def _get_prediction(db, config, case_id):
    row = db.execute("SELECT status,payload_json FROM predictions WHERE config=? AND case_id=?", (config, case_id)).fetchone()
    return (row["status"], json.loads(row["payload_json"])) if row else (None, None)


def _cache_embedding(db, cache_key, vector):
    db.execute("INSERT OR REPLACE INTO embeddings(cache_key,values_json,created_at) VALUES(?,?,?)", (cache_key, json.dumps(vector), iso_utc()))
    db.commit()


def _load_embedding(db, cache_key):
    row = db.execute("SELECT values_json FROM embeddings WHERE cache_key=?", (cache_key,)).fetchone()
    return json.loads(row["values_json"]) if row else None


def _embed_cache_wrapper(db, original_embed_many):
    async def cached_embed_many(texts, task_type):
        model = settings.GEMINI_EMBEDDING_MODEL
        keys = [sha256_text(f"{model}\0{task_type}\0{text}") for text in texts]
        vectors = [None] * len(texts)
        missing_by_key = {}
        for index, key in enumerate(keys):
            cached = _load_embedding(db, key)
            if cached is not None:
                vectors[index] = cached
            else:
                missing_by_key.setdefault(key, []).append(index)
        if missing_by_key:
            key_list = list(missing_by_key)
            distinct_texts = [texts[missing_by_key[key][0]] for key in key_list]
            generated = await original_embed_many(distinct_texts, task_type)
            if len(generated) != len(key_list):
                raise EvaluationRequestError("embedding", "INVALID_EMBEDDING_RESPONSE")
            for key, vector in zip(key_list, generated):
                _cache_embedding(db, key, vector)
                for index in missing_by_key[key]:
                    vectors[index] = vector
        return vectors
    return cached_embed_many


def _load_cases():
    raw = DATASET.read_bytes()
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(cases) != 200 or any(not row.get("synthetic") for row in cases):
        raise SystemExit("Expected exactly 200 explicitly synthetic scenarios")
    return cases, hashlib.sha256(raw).hexdigest()


def _case_order(cases, seed):
    rng = random.Random(seed)
    buckets = {}
    for row in cases:
        key = (row["ground_truth"], row["input"]["category"])
        buckets.setdefault(key, []).append(row)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    order = []
    while any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key]:
                order.append(buckets[key].pop())
    return order


def _safe_error_record(exc):
    if isinstance(exc, GeminiAPIError):
        return {
            "stage": exc.stage, "category": exc.category, "http_status": exc.status_code,
            "exception_type": exc.exception_type, "duration_seconds": exc.duration_seconds,
            "details": getattr(exc, "safe_details", {}),
            "retryable": getattr(exc, "retryable", False),
            "stop_run": getattr(exc, "stop_run", False),
            "retry_after_seconds": getattr(exc, "retry_after_seconds", None),
        }
    if isinstance(exc, EvaluationRequestError):
        return exc.as_dict()
    return {"category": "UNEXPECTED_ERROR", "exception_type": type(exc).__name__}


def _to_result_record(result, case, config, latency_ms, evidence=None):
    return {
        "case_id": case["case_id"], "ground_truth": case["ground_truth"],
        "scenario_group": case["scenario_group"], "category": case["input"]["category"],
        "fraud_positive": case["ground_truth"] == "fraudulent",
        "config": config, "status": "success", "prediction_source": "gemini",
        "flagged": result.recommendation in {"FLAG_FOR_REVIEW", "REJECT"} or bool(result.red_flags),
        "recommendation": result.recommendation, "score": result.authenticity_score,
        "model_used": result.model_used, "fallback_reason": None,
        "retrieved_evidence_count": len(evidence or []), "latency_ms": round(latency_ms, 2),
        "response": result.model_dump(mode="json"),
    }


def _negative_truth(row):
    return row["ground_truth"] in ("legitimate", "borderline")


def metrics(rows, latency_mode="end_to_end"):
    evaluated = [row for row in rows if row.get("status") == "success" and row.get("flagged") is not None]
    tp = sum(row["fraud_positive"] and row["flagged"] for row in evaluated)
    fp = sum(_negative_truth(row) and row["flagged"] for row in evaluated)
    fn = sum(row["fraud_positive"] and not row["flagged"] for row in evaluated)
    tn = sum(_negative_truth(row) and not row["flagged"] for row in evaluated)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    fpr = fp / (fp + tn) if fp + tn else None
    latencies = [row.get("latency_ms", 0.0) for row in rows if row.get("latency_ms") is not None]
    return {
        "attempted_cases": len(rows), "successful_predictions": len(evaluated),
        "prediction_coverage": round(len(evaluated) / len(rows), 4) if rows else None,
        # A local hybrid fallback is a completed system decision, not a
        # successful Gemini call. Track API coverage by prediction source.
        "api_success_rate": round(sum(row.get("status") == "success" and row.get("prediction_source") == "gemini" for row in rows) / len(rows), 4) if rows else None,
        "system_decision_coverage": round(sum(row.get("status") == "success" for row in rows) / len(rows), 4) if rows else None,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "false_positive_rate": round(fpr, 4) if fpr is not None else None,
        "end_to_end_latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(sorted(latencies)[min(len(latencies) - 1, math.ceil(0.95 * len(latencies)) - 1)], 2) if latencies else None,
        },
        "label_definition": "Fraudulent is positive; legitimate and borderline are negative. Gemini-only and Gemini+RAG classification metrics use successful model predictions only; failures are abstentions.",
    }


def _write_json_atomic(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _save_outputs(run_dir, db, run_config, status, stop_reason=None):
    outputs = {}
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = {row["case_id"]: row for row in cases}
    for config in ("gemini_only", "gemini_rag", "hybrid"):
        stored = db.execute("SELECT payload_json FROM predictions WHERE config=? ORDER BY case_id", (config,)).fetchall()
        rows = [json.loads(item["payload_json"]) for item in stored]
        rows.sort(key=lambda row: next((index for index, case in enumerate(cases) if case["case_id"] == row["case_id"]), 999))
        outputs[config] = rows
        _write_json_atomic(run_dir / f"{config}.partial.json", {"complete": False, "metrics": metrics(rows), "cases": rows})
        if rows:
            with (run_dir / f"{config}.partial.csv.tmp").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=[key for key in rows[0] if key != "response"])
                writer.writeheader()
                writer.writerows([{key: value for key, value in row.items() if key != "response"} for row in rows])
            os.replace(run_dir / f"{config}.partial.csv.tmp", run_dir / f"{config}.partial.csv")

    only_map = {row["case_id"]: row for row in outputs["gemini_only"] if row["status"] == "success"}
    rag_map = {row["case_id"]: row for row in outputs["gemini_rag"] if row["status"] == "success"}
    paired_ids = sorted(set(only_map) & set(rag_map))
    paired = {
        "shared_successful_case_count": len(paired_ids),
        "case_ids": paired_ids,
        "gemini_only": metrics([only_map[case_id] for case_id in paired_ids]),
        "gemini_rag": metrics([rag_map[case_id] for case_id in paired_ids]),
    }
    event_rows = db.execute("SELECT stage,outcome,category,http_status,details_json FROM api_events").fetchall()
    quota_errors = [
        {"stage": row["stage"], "category": row["category"], "http_status": row["http_status"], "details": json.loads(row["details_json"] or "{}")}
        for row in event_rows if row["http_status"] == 429
    ]
    report = {
        "status": status,
        "final": status == "complete",
        "run_config": run_config,
        "case_totals": {config: len(rows) for config, rows in outputs.items()},
        "pending_case_count": max(0, 200 - min(len(outputs["gemini_only"]), len(outputs["gemini_rag"]))),
        "metrics": {config: metrics(rows) for config, rows in outputs.items()},
        "paired_rag_ablation": paired,
        "quota_errors": quota_errors,
        "stop_reason": stop_reason,
        "resume_command": f".venv/bin/python evaluation/run_reproducible_gemini_eval.py --model {run_config['model']} --resume {run_dir}",
    }
    _write_json_atomic(run_dir / ("final_summary.json" if status == "complete" else "partial_summary.json"), report)
    return report


def _load_store(db, config, case_id):
    status, payload = _get_prediction(db, config, case_id)
    return status, payload


def _save_failure(db, config, case, error, latency_ms, evidence_count=0):
    details = _safe_error_record(error)
    retryable = details.get("retryable", False)
    wait_seconds = details.get("retry_after_seconds")
    resume_after = None
    if details.get("stop_run") and details.get("details", {}).get("resume_after_utc"):
        resume_after = details["details"]["resume_after_utc"]
    elif retryable and wait_seconds:
        resume_after = iso_utc(utc_now() + timedelta(seconds=wait_seconds))
    row = {
        "case_id": case["case_id"], "ground_truth": case["ground_truth"],
        "scenario_group": case["scenario_group"], "category": case["input"]["category"],
        "fraud_positive": case["ground_truth"] == "fraudulent", "config": config,
        "status": "retryable_failure" if retryable else "terminal_failure",
        "prediction_source": "none", "flagged": None, "recommendation": None,
        "model_used": None, "fallback_reason": details.get("category"),
        "error": details, "retry_after_utc": resume_after,
        "retrieved_evidence_count": evidence_count, "latency_ms": round(latency_ms, 2),
    }
    _save_prediction(db, config, case["case_id"], row["status"], row)
    return row


def _case_documents(case, directory):
    docs = []
    for index, doc in enumerate(case["input"].get("documents", []), 1):
        filename = f"{case['case_id'].lower()}-{index}.txt"
        (directory / filename).write_text(doc["content"], encoding="utf-8")
        docs.append({"doc_type": doc["doc_type"], "title": doc["title"], "file_url": f"/private-documents/{filename}", "verified": False})
    return docs


def _local_fallback(case, docs, evidence, elapsed_ms, reason):
    payload = case["input"]
    result = ai_verifier._verify_with_local_heuristics(
        title=payload["title"], category=payload["category"], story=payload["story"],
        goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
        beneficiary_type=payload.get("beneficiary_type", "SELF"),
        location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
        proof_documents=docs,
        supporting_document_count=len({item.get("file_url") for item in evidence if item.get("file_url")}),
    )
    return {
        "case_id": case["case_id"], "ground_truth": case["ground_truth"],
        "scenario_group": case["scenario_group"], "category": payload["category"],
        "fraud_positive": case["ground_truth"] == "fraudulent", "config": "hybrid",
        "status": "success", "prediction_source": "local_heuristics", "flagged": result.recommendation in {"FLAG_FOR_REVIEW", "REJECT"} or bool(result.red_flags),
        "recommendation": result.recommendation, "score": result.authenticity_score,
        "model_used": result.model_used, "fallback_reason": reason,
        "retrieved_evidence_count": len(evidence), "latency_ms": round(elapsed_ms, 2),
        "response": result.model_dump(mode="json"),
    }


async def _verify(case, config, docs, evidence, db, api_wrapper, run_state):
    payload = case["input"]
    started = time.perf_counter()
    try:
        result = await ai_verifier._verify_with_gemini(
            title=payload["title"], category=payload["category"], story=payload["story"],
            goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
            beneficiary_type=payload.get("beneficiary_type", "SELF"),
            location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
            proof_documents=docs,
            supporting_evidence=evidence,
        )
        elapsed = (time.perf_counter() - started) * 1000
        return _to_result_record(result, case, config, elapsed, evidence), None
    except (EvaluationRequestError, GeminiAPIError) as exc:
        elapsed = (time.perf_counter() - started) * 1000
        failure = _save_failure(db, config, case, exc, elapsed, len(evidence or []))
        if getattr(exc, "stop_run", False):
            run_state["stop_reason"] = _safe_error_record(exc)
        return failure, exc
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        failure = _save_failure(db, config, case, exc, elapsed, len(evidence or []))
        return failure, exc


async def _preflight(model, db, api_wrapper, previous_results=None):
    generation = {
        "contents": [{"parts": [{"text": "Reply with exactly: READY"}]}],
        "generationConfig": {"temperature": 0, "thinkingConfig": {"thinkingLevel": "LOW"}, "maxOutputTokens": 64},
    }
    embedding = {"requests": [{
        "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": "SevaFund quota and embedding preflight"}]},
        "taskType": "RETRIEVAL_QUERY",
    }]}
    results = {}
    for stage, model_name, payload in (("generation", model, generation), ("embedding", settings.GEMINI_EMBEDDING_MODEL, embedding)):
        previous = (previous_results or {}).get(stage, {})
        if previous.get("success") and previous.get("response_valid"):
            results[stage] = previous
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:{'generateContent' if stage == 'generation' else 'batchEmbedContents'}"
        started = time.perf_counter()
        try:
            response = await api_wrapper(url, settings.GEMINI_API_KEY, payload, stage, None)
            elapsed = round(time.perf_counter() - started, 3)
            if stage == "generation":
                candidate = (response.get("candidates") or [{}])[0]
                content = candidate.get("content") or {}
                parts = content.get("parts") or []
                text = "".join(item.get("text", "") for item in parts if isinstance(item, dict))
                valid = candidate.get("finishReason") == "STOP" and text.strip() == "READY"
            else:
                values = (response.get("embeddings") or [{}])[0].get("values")
                valid = bool(values)
            results[stage] = {"success": True, "response_valid": valid, "latency_seconds": elapsed, "http_status": 200}
        except (EvaluationRequestError, GeminiAPIError) as exc:
            results[stage] = {"success": False, **_safe_error_record(exc), "latency_seconds": round(time.perf_counter() - started, 3)}
        except Exception as exc:
            results[stage] = {"success": False, "exception_type": type(exc).__name__, "latency_seconds": round(time.perf_counter() - started, 3)}
    return results


async def _evaluate_cases(cases, db, run_state, api_wrapper):
    verifier_module = sys.modules[ai_verifier.__class__.__module__]
    original_verifier_post = verifier_module.post_json
    original_rag_post = rag.post_json
    original_embed_many = rag._embed_many
    verifier_module.post_json = api_wrapper
    rag.post_json = api_wrapper
    rag._embed_many = _embed_cache_wrapper(db, original_embed_many)
    old_upload = rag.UPLOAD_DIR
    try:
        with tempfile.TemporaryDirectory(prefix="seva-rag-200-") as temp_dir:
            rag.UPLOAD_DIR = Path(temp_dir)
            for case in cases:
                case_id = case["case_id"]
                db.current_case_id = case_id
                docs = _case_documents(case, rag.UPLOAD_DIR)
                # A completed Gemini-only result is reusable on resume.
                only_status, only_record = _load_store(db, "gemini_only", case_id)
                if only_status != "success":
                    only_record, _ = await _verify(case, "gemini_only", docs, [], db, api_wrapper, run_state)
                    if only_record["status"] == "success":
                        _save_prediction(db, "gemini_only", case_id, "success", only_record)
                if run_state.get("stop_reason"):
                    break

                rag_status, rag_record = _load_store(db, "gemini_rag", case_id)
                evidence = []
                retrieval_error = None
                retrieval_started = time.perf_counter()
                if rag_status != "success":
                    try:
                        chunks = await rag.retrieve_evidence(docs, _campaign_query(case["input"]))
                        evidence = _make_evidence(chunks)
                        if run_state.get("stop_reason"):
                            raise EvaluationRequestError("embedding", "DAILY_QUOTA_EXHAUSTED", stop_run=True)
                    except Exception as exc:
                        retrieval_error = exc
                        evidence = []
                    if run_state.get("stop_reason"):
                        break
                    rag_record, _ = await _verify(case, "gemini_rag", docs, evidence, db, api_wrapper, run_state)
                    if rag_record["status"] == "success":
                        rag_record["latency_ms"] += (time.perf_counter() - retrieval_started) * 1000
                        rag_record["retrieval_mode"] = "semantic_or_lexical_rag"
                        rag_record["retrieved_evidence_count"] = len(evidence)
                        _save_prediction(db, "gemini_rag", case_id, "success", rag_record)
                    elif retrieval_error:
                        rag_record["retrieval_error"] = _safe_error_record(retrieval_error)
                        _save_prediction(db, "gemini_rag", case_id, rag_record["status"], rag_record)
                if run_state.get("stop_reason"):
                    break

                hybrid_status, _ = _load_store(db, "hybrid", case_id)
                if hybrid_status != "success":
                    if rag_record and rag_record.get("status") == "success":
                        hybrid_record = {**rag_record, "config": "hybrid", "prediction_source": "gemini"}
                    else:
                        reason = (rag_record or {}).get("fallback_reason") or "GEMINI_RAG_FAILED"
                        hybrid_record = _local_fallback(
                            case, docs, evidence,
                            (rag_record or {}).get("latency_ms", (time.perf_counter() - retrieval_started) * 1000),
                            reason,
                        )
                    _save_prediction(db, "hybrid", case_id, "success", hybrid_record)
                _save_outputs(run_state["run_dir"], db, run_state["run_config"], "partial", run_state.get("stop_reason"))
    finally:
        verifier_module.post_json = original_verifier_post
        rag.post_json = original_rag_post
        rag._embed_many = original_embed_many
        rag.UPLOAD_DIR = old_upload


def _campaign_query(payload):
    location = f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", ")
    return f"{payload['title']} {payload['category']} {payload.get('beneficiary_name') or ''} {location} {payload['story']} {format_inr(payload['goal_amount'])}"


def _make_evidence(chunks):
    return [{
        "document_title": item["title"], "doc_type": item["doc_type"],
        "file_url": item.get("file_url"), "page": item.get("page"),
        "excerpt": item["text"], "relevance": item["relevance"],
    } for item in chunks]


def _default_run_dir(model):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).with_name("runs") / f"rigorous_{model.replace('.', '_')}_{stamp}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gemini-3.6-flash", help="Runtime-only generation model override")
    parser.add_argument("--resume", type=Path, help="Resume an existing run directory after its retry window or quota reset")
    parser.add_argument("--seed", type=int, default=20261115, help="Deterministic interleaving seed")
    args = parser.parse_args()
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is not configured; no requests were sent")

    cases, dataset_hash = _load_cases()
    settings.GEMINI_MODEL = args.model
    ai_verifier.model = args.model
    run_dir = args.resume.resolve() if args.resume else _default_run_dir(args.model).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    db = _init_db(run_dir / "state.sqlite3")

    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    verifier_hash = hashlib.sha256((ROOT / "app" / "services" / "ai_verifier.py").read_bytes()).hexdigest()
    run_config = {
        "model": args.model,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "thinking_level": "LOW",
        "max_output_tokens": 1024,
        "temperature": 0.1,
        "timeout_seconds": {"connect": CONNECT_TIMEOUT_SECONDS, "read": READ_TIMEOUT_SECONDS, "write": WRITE_TIMEOUT_SECONDS, "pool": POOL_TIMEOUT_SECONDS},
        "retry_policy": {"max_attempts": MAX_ATTEMPTS, "base_delay_seconds": BACKOFF_BASE_SECONDS, "max_delay_seconds": BACKOFF_MAX_SECONDS, "daily_quota_retries": 0},
        "execution": "sequential, one campaign at a time",
        "dataset": DATASET.name,
        "dataset_sha256": dataset_hash,
        "prompt_version": PROMPT_VERSION,
        "verifier_source_sha256": verifier_hash,
        "runner_source_sha256": source_hash,
        "seed": args.seed,
        "label_definition": "fraudulent is positive; legitimate and borderline are negative",
        "decision_definition": "flagged when recommendation is FLAG_FOR_REVIEW or REJECT or red_flags is nonempty",
        "production_configuration_modified": False,
        "scoring_thresholds_modified": False,
    }
    fingerprint = sha256_text(json.dumps(run_config, sort_keys=True))
    stored_fingerprint = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
    if stored_fingerprint and stored_fingerprint["value"] != fingerprint:
        previous = db.execute("SELECT value FROM metadata WHERE key='run_config'").fetchone()
        try:
            previous_config = json.loads(previous["value"]) if previous else None
        except (TypeError, ValueError):
            previous_config = None
        compatible_previous = {key: value for key, value in (previous_config or {}).items() if key != "runner_source_sha256"}
        compatible_current = {key: value for key, value in run_config.items() if key != "runner_source_sha256"}
        saved_case_count = db.execute("SELECT COUNT(*) AS n FROM predictions").fetchone()["n"]
        # Permit a runner-only code update for a preflight-blocked checkpoint.
        # Once any cases have predictions, keep the original runner version to
        # prevent mixing outputs from different evaluation implementations.
        if saved_case_count or compatible_previous != compatible_current:
            raise SystemExit("Resume configuration differs from the saved run; use a new run directory")
    db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('fingerprint',?)", (fingerprint,))
    db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('run_config',?)", (json.dumps(run_config, sort_keys=True),))
    db.commit()
    _write_json_atomic(run_dir / "run_config.json", run_config)

    run_state = {"run_dir": run_dir, "run_config": run_config, "stop_reason": None}
    api_wrapper = _api_wrapper(db, run_state)
    preflight_path = run_dir / "preflight.json"
    saved_preflight = None
    cached_preflight = None
    if args.resume and preflight_path.is_file():
        try:
            candidate = json.loads(preflight_path.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                saved_preflight = candidate
            if all(candidate.get(stage, {}).get("success") and candidate.get(stage, {}).get("response_valid") for stage in ("generation", "embedding")):
                cached_preflight = candidate
        except (OSError, ValueError, TypeError):
            saved_preflight = None
            cached_preflight = None
    preflight_results = cached_preflight or asyncio.run(_preflight(args.model, db, api_wrapper, saved_preflight))
    if cached_preflight is None:
        _write_json_atomic(preflight_path, preflight_results)
    preflight_good = all(preflight_results.get(stage, {}).get("success") and preflight_results.get(stage, {}).get("response_valid") for stage in ("generation", "embedding"))
    if not preflight_good:
        status = "blocked_at_preflight_quota" if any(
            item.get("details", {}).get("quota_kind") == "daily" or item.get("category") == "DAILY_QUOTA_EXHAUSTED"
            for item in preflight_results.values()
        ) else "blocked_at_preflight"
        report = _save_outputs(run_dir, db, run_config, status, next((item for item in preflight_results.values() if not item.get("success")), None))
        print(json.dumps({"report": report, "results_dir": str(run_dir)}, indent=2))
        db.close()
        return

    api_module = sys.modules[ai_verifier.__class__.__module__]
    original_post = api_module.post_json
    original_rag_post = rag.post_json
    original_embed_many = rag._embed_many
    # The runtime wrapper adds LOW thinking without touching production code.
    async def configured_post(url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        if stage == "generation":
            payload = {**payload, "generationConfig": {
                **payload.get("generationConfig", {}),
                "thinkingConfig": {"thinkingLevel": "LOW"},
                "maxOutputTokens": 1024,
            }}
        return await api_wrapper(url, api_key, payload, stage, timeout_seconds)
    api_module.post_json = configured_post
    rag.post_json = configured_post
    rag._embed_many = _embed_cache_wrapper(db, original_embed_many)
    try:
        ordered = _case_order(cases, args.seed)
        with tempfile.TemporaryDirectory(prefix="seva-full-eval-rag-") as temp_dir:
            rag.UPLOAD_DIR = Path(temp_dir)
            for case in ordered:
                if run_state.get("stop_reason"):
                    break
                await_case = asyncio.run(_evaluate_one_case(case, db, run_state))
                _save_outputs(run_dir, db, run_config, "partial", run_state.get("stop_reason"))
                if await_case == "daily_quota_stop":
                    break
        config_rows = {}
        for config in ("gemini_only", "gemini_rag", "hybrid"):
            query = db.execute("SELECT status,payload_json FROM predictions WHERE config=?", (config,)).fetchall()
            config_rows[config] = [json.loads(row["payload_json"]) for row in query]
        all_terminal = all(len(config_rows[c]) == 200 and all(row.get("status") in ("success", "terminal_failure") for row in config_rows[c]) for c in config_rows)
        final_status = "complete" if all_terminal and not run_state.get("stop_reason") else ("partial_quota_exhausted" if run_state.get("stop_reason", {}).get("category") == "DAILY_QUOTA_EXHAUSTED" else "partial")
        report = _save_outputs(run_dir, db, run_config, final_status, run_state.get("stop_reason"))
        print(json.dumps({"report": report, "results_dir": str(run_dir)}, indent=2))
    finally:
        api_module.post_json = original_post
        rag.post_json = original_rag_post
        rag._embed_many = original_embed_many
        db.close()


async def _evaluate_one_case(case, db, run_state):
    case_id = case["case_id"]
    db.current_case_id = case_id
    rag_dir = rag.UPLOAD_DIR
    docs = _case_documents(case, rag_dir)
    run_state["stop_reason"] = None

    only_status, only_record = _load_store(db, "gemini_only", case_id)
    if only_status != "success":
        started = time.perf_counter()
        try:
            result = await _verify_for_config(case, docs, [], "gemini_only")
            only_record = _to_result_record(result, case, "gemini_only", (time.perf_counter() - started) * 1000, [])
            _save_prediction(db, "gemini_only", case_id, "success", only_record)
        except (GeminiAPIError, EvaluationRequestError) as exc:
            only_record = _save_failure(db, "gemini_only", case, exc, (time.perf_counter() - started) * 1000)
            if getattr(exc, "stop_run", False):
                run_state["stop_reason"] = _safe_error_record(exc)
    if run_state.get("stop_reason"):
        return "daily_quota_stop"

    rag_status, rag_record = _load_store(db, "gemini_rag", case_id)
    evidence = []
    if rag_status != "success":
        retrieval_started = time.perf_counter()
        try:
            chunks = await rag.retrieve_evidence(docs, _campaign_query(case["input"]))
            evidence = _make_evidence(chunks)
            if run_state.get("stop_reason"):
                raise GeminiAPIError("embedding", "DAILY_QUOTA_EXHAUSTED", 429)
        except (GeminiAPIError, EvaluationRequestError) as exc:
            evidence = []
            retrieval_error = exc
            if getattr(exc, "stop_run", False) or run_state.get("stop_reason"):
                run_state["stop_reason"] = _safe_error_record(exc)
                return "daily_quota_stop"
        else:
            retrieval_error = None
        started = time.perf_counter()
        try:
            result = await _verify_for_config(case, docs, evidence, "gemini_rag")
            rag_record = _to_result_record(result, case, "gemini_rag", (time.perf_counter() - retrieval_started) * 1000, evidence)
            rag_record["retrieved_evidence_count"] = len(evidence)
            rag_record["retrieval_latency_ms"] = round((started - retrieval_started) * 1000, 2)
            _save_prediction(db, "gemini_rag", case_id, "success", rag_record)
        except (GeminiAPIError, EvaluationRequestError) as exc:
            rag_record = _save_failure(db, "gemini_rag", case, exc, (time.perf_counter() - retrieval_started) * 1000, len(evidence))
            if retrieval_error:
                rag_record["retrieval_error"] = _safe_error_record(retrieval_error)
            _save_prediction(db, "gemini_rag", case_id, rag_record["status"], rag_record)
            if getattr(exc, "stop_run", False):
                run_state["stop_reason"] = _safe_error_record(exc)
        if run_state.get("stop_reason"):
            # RAG result failure is recorded; hybrid fallback is still a valid
            # local decision for the current case, but the run stops afterwards.
            pass

    if rag_record and rag_record.get("status") == "success":
        hybrid = {**rag_record, "config": "hybrid", "prediction_source": "gemini"}
    else:
        hybrid = _local_fallback(
            case, docs, evidence,
            rag_record.get("latency_ms", 0.0) if rag_record else 0.0,
            (rag_record or {}).get("fallback_reason") or "GEMINI_RAG_FAILED",
        )
    _save_prediction(db, "hybrid", case_id, "success", hybrid)
    return "daily_quota_stop" if run_state.get("stop_reason") else "ok"


async def _verify_for_config(case, docs, evidence, config):
    payload = case["input"]
    return await ai_verifier._verify_with_gemini(
        title=payload["title"], category=payload["category"], story=payload["story"],
        goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
        beneficiary_type=payload.get("beneficiary_type", "SELF"),
        location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
        proof_documents=docs, supporting_evidence=evidence,
    )


if __name__ == "__main__":
    main()
