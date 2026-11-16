"""Compare the four campaign verification configurations on the synthetic holdout."""
import argparse
import asyncio
import csv
import json
import random
import statistics
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path(__file__).with_name("fundraising_scenarios.jsonl")
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services import rag
from app.services.ai_verifier import ai_verifier
from app.services.gemini_api import GeminiAPIError, post_json
from app.services.fraud_detector import format_inr

LOCAL_MODEL = "crowdfund-india-trust-v1"


def is_flagged(result):
    return result.recommendation in {"FLAG_FOR_REVIEW", "REJECT"} or bool(result.red_flags)


def metrics(rows):
    evaluated = [row for row in rows if row["flagged"] is not None]
    tp = sum(row["fraud_positive"] and row["flagged"] for row in evaluated)
    fp = sum(not row["fraud_positive"] and row["flagged"] for row in evaluated)
    fn = sum(row["fraud_positive"] and not row["flagged"] for row in evaluated)
    tn = sum(not row["fraud_positive"] and not row["flagged"] for row in evaluated)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    fpr = fp / (fp + tn) if fp + tn else None
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "cases": len(rows),
        "evaluated_cases": len(evaluated),
        "coverage": round(len(evaluated) / len(rows), 4) if rows else None,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "false_positive_rate": round(fpr, 4) if fpr is not None else None,
        "latency_ms_mean": round(statistics.mean(latencies), 2) if latencies else None,
    }


async def preflight():
    endpoints = [
        ("generation", f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent", {
            "contents": [{"parts": [{"text": "Reply with the word ready."}]}],
            "generationConfig": {"temperature": 0},
        }),
        ("embedding", f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents", {
            "requests": [{"model": f"models/{settings.GEMINI_EMBEDDING_MODEL}", "content": {"parts": [{"text": "configuration comparison preflight"}]}, "taskType": "RETRIEVAL_DOCUMENT"}],
        }),
    ]
    for stage, url, payload in endpoints:
        try:
            await post_json(
                url, settings.GEMINI_API_KEY, payload, stage,
                httpx.Timeout(connect=10, read=180, write=20, pool=10), max_attempts=1,
            )
        except GeminiAPIError as exc:
            raise RuntimeError(
                f"{stage}:{exc.category}:HTTP_{exc.status_code or 'NA'}:"
                f"{exc.exception_type or 'NO_EXCEPTION'}:{exc.duration_seconds or 'NA'}s"
            ) from None


def input_rows(cases, scratch):
    rows = []
    for case in cases:
        payload = dict(case["input"])
        docs = []
        for index, doc in enumerate(payload.get("documents", []), start=1):
            filename = f"{case['case_id'].lower()}-{index}.txt"
            (scratch / filename).write_text(doc["content"], encoding="utf-8")
            docs.append({"doc_type": doc["doc_type"], "title": doc["title"], "file_url": f"/private-documents/{filename}", "verified": False})
        rows.append((case, payload, docs))
    return rows


def local_result(payload, docs, evidence):
    return ai_verifier._verify_with_local_heuristics(
        title=payload["title"], category=payload["category"], story=payload["story"],
        goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
        beneficiary_type=payload.get("beneficiary_type", "SELF"),
        location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
        proof_documents=docs,
        supporting_document_count=len({item.get("file_url") for item in evidence if item.get("file_url")}),
    )


def evidence_query(payload):
    location = f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", ")
    return f"{payload['title']} {payload['category']} {payload.get('beneficiary_name') or ''} {location} {payload['story']} {format_inr(payload['goal_amount'])}"


async def generate(payload, docs, evidence):
    try:
        result = await ai_verifier._verify_with_gemini(
            title=payload["title"], category=payload["category"], story=payload["story"],
            goal_amount=payload["goal_amount"], beneficiary_name=payload.get("beneficiary_name"),
            beneficiary_type=payload.get("beneficiary_type", "SELF"),
            location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
            proof_documents=docs, supporting_evidence=evidence,
        )
        return result, None
    except GeminiAPIError as exc:
        return None, f"{exc.stage}:{exc.category}"
    except Exception as exc:
        return None, f"generation:UNEXPECTED_{type(exc).__name__}"


def prediction(case, payload, result, reason, elapsed_ms, evidence_count=0):
    return {
        "case_id": case["case_id"], "ground_truth": case["ground_truth"],
        "scenario_group": case["scenario_group"], "category": payload["category"],
        "fraud_positive": case["ground_truth"] == "fraudulent",
        "flagged": is_flagged(result) if result is not None else None,
        "recommendation": result.recommendation if result is not None else None,
        "model_used": result.model_used if result is not None else None,
        "fallback_reason": reason, "retrieved_evidence_count": evidence_count,
        "latency_ms": round(elapsed_ms, 2),
    }


async def evaluate(cases):
    outputs = {"heuristics_lexical": [], "gemini_only": [], "gemini_rag": [], "gemini_rag_heuristics": []}
    errors = Counter()
    api_key = settings.GEMINI_API_KEY
    with tempfile.TemporaryDirectory(prefix="crowdfund-config-eval-") as scratch_dir:
        scratch = Path(scratch_dir)
        rag.UPLOAD_DIR = scratch
        prepared = input_rows(cases, scratch)
        # Python heuristics + lexical retrieval baseline (no embedding or generation calls).
        settings.GEMINI_API_KEY = ""
        ai_verifier.api_key = ""
        for case, payload, docs in prepared:
            started = time.perf_counter()
            evidence_chunks = await rag.retrieve_evidence(docs, evidence_query(payload))
            evidence = [{"document_title": c["title"], "doc_type": c["doc_type"], "file_url": c.get("file_url"), "page": c.get("page"), "excerpt": c["text"], "relevance": c["relevance"]} for c in evidence_chunks]
            result = local_result(payload, docs, evidence)
            result.supporting_evidence = evidence
            outputs["heuristics_lexical"].append(prediction(case, payload, result, None, (time.perf_counter() - started) * 1000, len(evidence)))

        settings.GEMINI_API_KEY = api_key
        ai_verifier.api_key = settings.GEMINI_API_KEY
        # Interleave ground-truth/category groups so transient quota changes do
        # not leave all campaigns from one category at the end of the run.
        rng = random.Random(20261115)
        buckets = {}
        for item in prepared:
            buckets.setdefault((item[0]["ground_truth"], item[1]["category"]), []).append(item)
        for bucket in buckets.values():
            rng.shuffle(bucket)
        interleaved = []
        while any(buckets.values()):
            for key in sorted(buckets):
                if buckets[key]:
                    interleaved.append(buckets[key].pop())
        for case, payload, docs in interleaved:
            started = time.perf_counter()
            # Gemini sees campaign fields and attachment count, but no document text.
            gemini_only, only_error = await generate(payload, docs, [])
            only_elapsed = (time.perf_counter() - started) * 1000
            outputs["gemini_only"].append(prediction(case, payload, gemini_only, only_error, only_elapsed))
            if only_error:
                errors[f"gemini_only:{only_error}"] += 1

            started = time.perf_counter()
            evidence_chunks = await rag.retrieve_evidence(docs, evidence_query(payload))
            evidence = [{"document_title": c["title"], "doc_type": c["doc_type"], "file_url": c.get("file_url"), "page": c.get("page"), "excerpt": c["text"], "relevance": c["relevance"]} for c in evidence_chunks]
            gemini_rag, rag_error = await generate(payload, docs, evidence)
            rag_elapsed = (time.perf_counter() - started) * 1000
            outputs["gemini_rag"].append(prediction(case, payload, gemini_rag, rag_error, rag_elapsed, len(evidence)))
            if rag_error:
                errors[f"gemini_rag:{rag_error}"] += 1

            if gemini_rag is not None:
                hybrid = gemini_rag
                hybrid_error = None
            else:
                hybrid = local_result(payload, docs, evidence)
                hybrid.supporting_evidence = evidence
                hybrid_error = rag_error
            outputs["gemini_rag_heuristics"].append(prediction(case, payload, hybrid, hybrid_error, rag_elapsed, len(evidence)))
    return outputs, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-gemini", action="store_true", help="Make Gemini generation and embedding API calls")
    args = parser.parse_args()
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(cases) != 200 or any(not case.get("synthetic") for case in cases):
        raise SystemExit("Expected exactly 200 explicitly synthetic cases")
    if not args.live_gemini or not settings.GEMINI_API_KEY:
        raise SystemExit("This comparison requires --live-gemini and a configured GEMINI_API_KEY")
    run_id = datetime.now(timezone.utc).strftime("comparison_%Y%m%dT%H%M%SZ")
    run_dir = Path(__file__).with_name("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        asyncio.run(preflight())
    except RuntimeError as exc:
        report = {
            "status": "blocked_at_preflight", "dataset": DATASET.name,
            "synthetic": True, "case_count": len(cases), "cases_sent": 0,
            "reason": str(exc), "models": {"generation": settings.GEMINI_MODEL, "embedding": settings.GEMINI_EMBEDDING_MODEL},
        }
        (run_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({**report, "results_path": str(run_dir / "results.json")}, indent=2))
        return

    outputs, errors = asyncio.run(evaluate(cases))
    labels = {
        "heuristics_lexical": "Python heuristics + lexical retrieval",
        "gemini_only": "Gemini only",
        "gemini_rag": "Gemini + RAG",
        "gemini_rag_heuristics": "Gemini + RAG + heuristics fallback",
    }
    report = {
        "status": "complete", "dataset": DATASET.name, "synthetic": True,
        "models": {"generation": settings.GEMINI_MODEL, "embedding": settings.GEMINI_EMBEDDING_MODEL},
        "decision_rule": "Flagged when recommendation is FLAG_FOR_REVIEW or REJECT, or red_flags is non-empty.",
        "binary_mapping": "Fraudulent is positive; legitimate and borderline are negative.",
        "metric_policy": "Gemini-only configurations report metrics on successful model responses; coverage gives the fraction of the 200 holdout cases evaluated. The heuristic-fallback configuration evaluates all cases.",
        "configurations": {labels[name]: metrics(rows) for name, rows in outputs.items()},
        "fallback_error_counts": dict(errors),
    }
    (run_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for config, rows in outputs.items():
        with (run_dir / f"{config}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({**report, "results_path": str(run_dir / "results.json")}, indent=2))


if __name__ == "__main__":
    main()
