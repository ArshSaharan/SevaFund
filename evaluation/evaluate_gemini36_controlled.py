"""Controlled, staged Gemini 3.6 Flash evaluation; never launches the 200-case set."""
import argparse
import asyncio
import csv
import json
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path(__file__).with_name("fundraising_scenarios.jsonl")
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services import rag
from app.services.ai_verifier import ai_verifier
from app.services.gemini_api import GeminiAPIError
from app.services.fraud_detector import format_inr

DIAGNOSTIC_IDS = ["SYN-001", "SYN-061", "SYN-121", "SYN-161", "SYN-181"]
REPRESENTATIVE_IDS = [
    "SYN-001", "SYN-006", "SYN-011", "SYN-016",       # legitimate medical
    "SYN-061", "SYN-066", "SYN-071", "SYN-076",       # fraudulent medical
    "SYN-121", "SYN-122", "SYN-123", "SYN-124",       # borderline medical
    "SYN-161", "SYN-165", "SYN-169",                   # legitimate education/social
    "SYN-181", "SYN-185", "SYN-189",                   # fraudulent education/social
    "SYN-125", "SYN-126",                               # borderline education/community
]
HTTP_TIMEOUT = httpx.Timeout(connect=10, read=90, write=20, pool=10)


def is_flagged(result):
    return result.recommendation in {"FLAG_FOR_REVIEW", "REJECT"} or bool(result.red_flags)


def metric_summary(rows):
    evaluated = [row for row in rows if row["flagged"] is not None]
    tp = sum(row["fraud_positive"] and row["flagged"] for row in evaluated)
    fp = sum(not row["fraud_positive"] and row["flagged"] for row in evaluated)
    fn = sum(row["fraud_positive"] and not row["flagged"] for row in evaluated)
    tn = sum(not row["fraud_positive"] and not row["flagged"] for row in evaluated)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    fpr = fp / (fp + tn) if fp + tn else None
    latencies = [row["latency_ms"] for row in rows]
    return {
        "cases": len(rows),
        "gemini_successes": sum(row["prediction_source"] == "gemini" for row in rows),
        "local_fallbacks": sum(row["prediction_source"] == "local_heuristics" for row in rows),
        "abstentions": sum(row["flagged"] is None for row in rows),
        "evaluated_predictions": len(evaluated),
        "coverage": round(len(evaluated) / len(rows), 4) if rows else None,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "false_positive_rate": round(fpr, 4) if fpr is not None else None,
        "end_to_end_latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(sorted(latencies)[min(len(latencies) - 1, int(0.95 * len(latencies)))] , 2) if latencies else None,
        },
    }


def make_evidence(chunks):
    return [{
        "document_title": chunk["title"], "doc_type": chunk["doc_type"],
        "file_url": chunk.get("file_url"), "page": chunk.get("page"),
        "excerpt": chunk["text"], "relevance": chunk["relevance"],
    } for chunk in chunks]


def campaign_query(payload):
    location = f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", ")
    return f"{payload['title']} {payload['category']} {payload.get('beneficiary_name') or ''} {location} {payload['story']} {format_inr(payload['goal_amount'])}"


def local_fallback(case, payload, docs, evidence):
    result = ai_verifier._verify_with_local_heuristics(
        title=payload["title"], category=payload["category"], story=payload["story"],
        goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
        beneficiary_type=payload.get("beneficiary_type", "SELF"),
        location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
        proof_documents=docs,
        supporting_document_count=len({item.get("file_url") for item in evidence if item.get("file_url")}),
    )
    result.supporting_evidence = evidence
    result.fallback_reason = "GEMINI_RAG_GENERATION_FAILED"
    return result


def gemini_failure_reason(exc):
    status = f":HTTP_{exc.status_code}" if exc.status_code else ""
    return f"{exc.stage}:{exc.category}{status}"


def contains_quota_denial(rows):
    for row in rows:
        if "HTTP_429" in str(row.get("fallback_reason")):
            return True
        if any(event.get("http_status") == 429 for event in row.get("embedding_errors", [])):
            return True
    return False


def make_record(case, payload, result, source, reason, latency_ms, evidence_count=0):
    return {
        "case_id": case["case_id"],
        "ground_truth": case["ground_truth"],
        "scenario_group": case["scenario_group"],
        "category": payload["category"],
        "fraud_positive": case["ground_truth"] == "fraudulent",
        "flagged": is_flagged(result) if result is not None else None,
        "recommendation": result.recommendation if result is not None else None,
        "score": result.authenticity_score if result is not None else None,
        "model_used": result.model_used if result is not None else None,
        "prediction_source": source,
        "fallback_reason": reason,
        "retrieved_evidence_count": evidence_count,
        "latency_ms": round(latency_ms, 2),
    }


async def preflight(model):
    generation_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    embedding_url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents"
    headers = {"x-goog-api-key": settings.GEMINI_API_KEY}
    generation_payload = {
        "contents": [{"parts": [{"text": "Reply with exactly: READY"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 256, "thinkingConfig": {"thinkingLevel": "LOW"}},
    }
    embedding_payload = {"requests": [{
        "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": "SevaFund RAG preflight"}]},
        "taskType": "RETRIEVAL_QUERY",
    }]}
    results = {}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for name, url, payload in (("generation", generation_url, generation_payload), ("embedding", embedding_url, embedding_payload)):
            started = time.perf_counter()
            try:
                response = await client.post(url, headers=headers, json=payload)
                elapsed = round(time.perf_counter() - started, 3)
                entry = {"success": response.status_code == 200, "http_status": response.status_code, "latency_seconds": elapsed}
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                if response.status_code == 200 and name == "generation":
                    candidates = body.get("candidates", []) if isinstance(body, dict) else []
                    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
                    content = candidate.get("content", {})
                    parts = content.get("parts", []) if isinstance(content, dict) else []
                    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                    entry["response_valid"] = candidate.get("finishReason") == "STOP" and text.strip() == "READY"
                    entry["finish_reason"] = candidate.get("finishReason")
                elif response.status_code == 200:
                    entries = body.get("embeddings", []) if isinstance(body, dict) else []
                    entry["response_valid"] = len(entries) == 1 and isinstance(entries[0], dict) and bool(entries[0].get("values"))
                else:
                    error = body.get("error", {}) if isinstance(body, dict) else {}
                    entry["provider_status"] = error.get("status") if isinstance(error, dict) else None
                    entry["quota_denied"] = response.status_code == 429
                results[name] = entry
            except httpx.RequestError as exc:
                results[name] = {
                    "success": False,
                    "latency_seconds": round(time.perf_counter() - started, 3),
                    "exception_type": type(exc).__name__,
                    "failure_phase": timeout_phase(exc),
                }
    return results


def timeout_phase(exc):
    if isinstance(exc, httpx.ConnectTimeout):
        return "connect"
    if isinstance(exc, httpx.ReadTimeout):
        return "read"
    if isinstance(exc, httpx.WriteTimeout):
        return "write"
    if isinstance(exc, httpx.PoolTimeout):
        return "pool"
    return "network_or_unknown_timeout"


async def run_case(case, scratch, api_events):
    payload = dict(case["input"])
    docs = []
    for index, doc in enumerate(payload.get("documents", []), start=1):
        filename = f"{case['case_id'].lower()}-{index}.txt"
        (scratch / filename).write_text(doc["content"], encoding="utf-8")
        docs.append({"doc_type": doc["doc_type"], "title": doc["title"], "file_url": f"/private-documents/{filename}", "verified": False})

    gemini_only_started = time.perf_counter()
    gemini_only_result = None
    gemini_only_error = None
    try:
        gemini_only_result = await ai_verifier._verify_with_gemini(
            title=payload["title"], category=payload["category"], story=payload["story"],
            goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
            beneficiary_type=payload.get("beneficiary_type", "SELF"),
            location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
            proof_documents=docs, supporting_evidence=[],
        )
    except GeminiAPIError as exc:
        gemini_only_error = gemini_failure_reason(exc)
    except Exception as exc:
        gemini_only_error = f"generation:UNEXPECTED_{type(exc).__name__}"
    gemini_only_ms = (time.perf_counter() - gemini_only_started) * 1000
    gemini_only_record = make_record(case, payload, gemini_only_result, "gemini" if gemini_only_result else "abstention", gemini_only_error, gemini_only_ms)

    rag_started = time.perf_counter()
    try:
        chunks = await rag.retrieve_evidence(docs, campaign_query(payload))
        evidence = make_evidence(chunks)
        gemini_rag_result = await ai_verifier._verify_with_gemini(
            title=payload["title"], category=payload["category"], story=payload["story"],
            goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
            beneficiary_type=payload.get("beneficiary_type", "SELF"),
            location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
            proof_documents=docs, supporting_evidence=evidence,
        )
        rag_error = None
    except GeminiAPIError as exc:
        evidence = locals().get("evidence", [])
        gemini_rag_result = None
        rag_error = gemini_failure_reason(exc)
    except Exception as exc:
        evidence = locals().get("evidence", [])
        gemini_rag_result = None
        rag_error = f"generation:UNEXPECTED_{type(exc).__name__}"
    rag_ms = (time.perf_counter() - rag_started) * 1000
    rag_record = make_record(case, payload, gemini_rag_result, "gemini" if gemini_rag_result else "abstention", rag_error, rag_ms, len(evidence))

    if gemini_rag_result is not None:
        hybrid_result = gemini_rag_result
        hybrid_source = "gemini"
        hybrid_error = None
        hybrid_ms = rag_ms
    else:
        fallback_started = time.perf_counter()
        hybrid_result = local_fallback(case, payload, docs, evidence)
        hybrid_source = "local_heuristics"
        hybrid_error = rag_error or "NO_GEMINI_RESULT"
        hybrid_ms = rag_ms + (time.perf_counter() - fallback_started) * 1000
    hybrid_record = make_record(case, payload, hybrid_result, hybrid_source, hybrid_error, hybrid_ms, len(evidence))
    if api_events:
        retrieval_failures = [event for event in api_events if not event["success"]]
        retrieval_mode = "LEXICAL_FALLBACK" if retrieval_failures else "SEMANTIC_EMBEDDINGS"
    else:
        retrieval_failures = []
        retrieval_mode = "NO_DOCUMENT_EMBEDDINGS"
    for record in (rag_record, hybrid_record):
        record["retrieval_mode"] = retrieval_mode
        record["embedding_errors"] = retrieval_failures
    return {"gemini_only": gemini_only_record, "gemini_rag": rag_record, "hybrid": hybrid_record}


async def evaluate_stage(cases, rag_dir):
    outputs = {"gemini_only": {}, "gemini_rag": {}, "hybrid": {}}
    import importlib
    verifier_module = importlib.import_module("app.services.ai_verifier")
    original_verifier_post = verifier_module.post_json
    original_rag_post = rag.post_json

    async def one_attempt_low_thinking(url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        if stage == "generation":
            payload = {**payload, "generationConfig": {
                **payload.get("generationConfig", {}),
                "thinkingConfig": {"thinkingLevel": "LOW"},
                "maxOutputTokens": 1024,
            }}
            timeout_seconds = HTTP_TIMEOUT
        return await original_verifier_post(url, api_key, payload, stage, timeout_seconds, max_attempts=1)

    current = {"events": []}

    async def rag_one_attempt(url, api_key, payload, stage, timeout_seconds, max_attempts=2):
        started = time.perf_counter()
        try:
            response = await original_rag_post(url, api_key, payload, stage, timeout_seconds, max_attempts=1)
            current["events"].append({"stage": stage, "success": True, "duration_seconds": round(time.perf_counter() - started, 3)})
            return response
        except GeminiAPIError as exc:
            current["events"].append({
                "stage": stage, "success": False, "category": exc.category,
                "http_status": exc.status_code, "exception_type": exc.exception_type,
                "duration_seconds": exc.duration_seconds,
            })
            raise

    verifier_module.post_json = one_attempt_low_thinking
    rag.post_json = rag_one_attempt
    old_upload_dir = rag.UPLOAD_DIR
    try:
        rag.UPLOAD_DIR = rag_dir
        for case in cases:
            current["events"] = []
            result = await run_case(case, rag_dir, current["events"])
            for config in outputs:
                outputs[config][case["case_id"]] = result[config]
    finally:
        verifier_module.post_json = original_verifier_post
        rag.post_json = original_rag_post
        rag.UPLOAD_DIR = old_upload_dir
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gemini-3.6-flash", help="Runtime-only model override; does not edit application configuration")
    args = parser.parse_args()
    if args.model not in {"gemini-3.6-flash", "gemini-3.8-flash"}:
        raise SystemExit("Use one of the two compared Flash models")
    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is not configured; no requests were sent")

    # Runtime-only overrides: the saved .env and application defaults are untouched.
    settings.GEMINI_MODEL = args.model
    ai_verifier.model = args.model
    all_cases = {item["case_id"]: item for item in (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip())}
    if len(all_cases) != 200 or any(not item.get("synthetic") for item in all_cases.values()):
        raise SystemExit("Expected the existing 200-case synthetic dataset")
    diagnostic_cases = [all_cases[item] for item in DIAGNOSTIC_IDS]
    representative_cases = [all_cases[item] for item in REPRESENTATIVE_IDS]

    run_id = datetime.now(timezone.utc).strftime(f"controlled_{args.model.replace('.', '_')}_%Y%m%dT%H%M%SZ")
    run_dir = Path(__file__).with_name("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "model": args.model,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "dataset": DATASET.name,
        "synthetic": True,
        "production_configuration_modified": False,
        "fraud_algorithm_or_thresholds_modified": False,
        "automatic_retries": 0,
        "thinking_level": "LOW",
        "max_output_tokens": 1024,
        "httpx_timeouts_seconds": {"connect": 10, "read": 90, "write": 20, "pool": 10},
        "metric_policy": "Gemini-only and Gemini+RAG metrics include only Gemini-success predictions; failed generations are abstentions. Hybrid uses local heuristics only when Gemini+RAG fails. Fraudulent is positive; legitimate and borderline are negative.",
        "selection": {"diagnostic_ids": DIAGNOSTIC_IDS, "representative_ids": REPRESENTATIVE_IDS},
    }
    preflight_results = asyncio.run(preflight(args.model))
    report["preflight"] = preflight_results
    preflight_passed = all(
        preflight_results[name].get("success") and preflight_results[name].get("response_valid")
        for name in ("generation", "embedding")
    )
    if not preflight_passed:
        report.update({"status": "blocked_at_preflight", "cases_evaluated": 0, "diagnostic_gate_passed": False, "representative20_started": False})
        write_reports(run_dir, report, {})
        print(json.dumps({**report, "results_dir": str(run_dir)}, indent=2))
        return

    with tempfile.TemporaryDirectory(prefix="gemini36-controlled-rag-") as tmp:
        rag_dir = Path(tmp)
        diagnostic_outputs = asyncio.run(evaluate_stage(diagnostic_cases, rag_dir))
        diagnostic_summaries = {key: metric_summary(list(rows.values())) for key, rows in diagnostic_outputs.items()}
        rag_records = list(diagnostic_outputs["gemini_rag"].values())
        label_coverage = {label: any(row["ground_truth"] == label and row["prediction_source"] == "gemini" for row in rag_records) for label in ("legitimate", "fraudulent", "borderline")}
        gate = (
            diagnostic_summaries["gemini_only"]["gemini_successes"] >= 4
            and diagnostic_summaries["gemini_rag"]["gemini_successes"] >= 4
            and all(label_coverage.values())
            and not any(contains_quota_denial(list(rows.values())) for rows in diagnostic_outputs.values())
        )
        report["diagnostic5"] = {
            "summaries": diagnostic_summaries,
            "gemini_rag_label_coverage": label_coverage,
            "gate_passed": gate,
            "cases": {key: list(rows.values()) for key, rows in diagnostic_outputs.items()},
        }
        outputs_to_save = {key: dict(rows) for key, rows in diagnostic_outputs.items()}
        if gate:
            existing_ids = set(DIAGNOSTIC_IDS)
            remaining = [case for case in representative_cases if case["case_id"] not in existing_ids]
            extra_outputs = asyncio.run(evaluate_stage(remaining, rag_dir))
            for config, rows in extra_outputs.items():
                outputs_to_save[config].update(rows)
            report["representative20"] = {key: metric_summary(list(rows.values())) for key, rows in outputs_to_save.items()}
            report["representative20_started"] = True
            report["status"] = "diagnostic_and_representative_complete"
            report["cases_evaluated"] = len(REPRESENTATIVE_IDS)
        else:
            report["representative20_started"] = False
            report["status"] = "diagnostic_gate_failed"
            report["cases_evaluated"] = len(DIAGNOSTIC_IDS)
        report["full200_started"] = False
        report["quota_note"] = "Gemini does not expose remaining project quota through this API call; stop before the 200-case run if any request returns HTTP 429. The 20-case run is a screening check, not proof of sufficient daily quota for 200 cases."
        write_reports(run_dir, report, outputs_to_save)
        print(json.dumps({**report, "results_dir": str(run_dir)}, indent=2))


def write_reports(run_dir, report, outputs):
    (run_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for config, rows_by_id in outputs.items():
        rows = list(rows_by_id.values())
        if not rows:
            continue
        (run_dir / f"{config}.json").write_text(json.dumps({"metrics": metric_summary(rows), "cases": rows}, indent=2) + "\n", encoding="utf-8")
        with (run_dir / f"{config}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
