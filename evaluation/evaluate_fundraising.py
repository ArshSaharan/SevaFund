"""Run the deterministic local/RAG fallback against the synthetic held-out set."""
import argparse
import asyncio
import csv
import json
import math
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
import httpx
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path(__file__).with_name("fundraising_scenarios.jsonl")
RESULTS = Path(__file__).with_name("results.json")
PREDICTIONS = Path(__file__).with_name("predictions.csv")
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.ai_verifier import ai_verifier
from app.services import rag


def score_metrics(rows):
    tp = sum(r["fraud_positive"] and r["flagged"] for r in rows)
    fp = sum((not r["fraud_positive"]) and r["flagged"] for r in rows)
    fn = sum(r["fraud_positive"] and (not r["flagged"]) for r in rows)
    tn = sum((not r["fraud_positive"]) and (not r["flagged"]) for r in rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None
    fpr = fp / (fp + tn) if fp + tn else None
    latencies = sorted(r["latency_ms"] for r in rows)
    p95 = latencies[min(len(latencies) - 1, math.ceil(0.95 * len(latencies)) - 1)]
    return {
        "cases": len(rows),
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "false_positive_rate": round(fpr, 4) if fpr is not None else None,
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2),
            "median": round(statistics.median(latencies), 2),
            "p95": round(p95, 2),
        },
    }


async def gemini_preflight():
    """Verify both Gemini endpoints before spending time on a live evaluation."""
    endpoints = [
        ("generation", f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent", {
            "contents": [{"parts": [{"text": "Reply with the word ready."}]}],
            "generationConfig": {"temperature": 0},
        }),
        ("embeddings", f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents", {
            "requests": [{
                "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                "content": {"parts": [{"text": "fundraising evaluation preflight"}]},
                "taskType": "RETRIEVAL_DOCUMENT",
            }],
        }),
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        for name, url, payload in endpoints:
            response = await client.post(url, headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=payload)
            if response.status_code != 200:
                raise SystemExit(f"Gemini {name} preflight failed (HTTP {response.status_code}); evaluation stopped before processing any cases.")


async def evaluate(cases):
    predictions = []
    with tempfile.TemporaryDirectory(prefix="crowdfund-rag-eval-") as scratch:
        rag.UPLOAD_DIR = Path(scratch)
        for case in cases:
            payload = dict(case["input"])
            payload["documents"] = []
            for index, doc in enumerate(case["input"].get("documents", []), start=1):
                filename = f"{case['case_id'].lower()}-{index}.txt"
                (Path(scratch) / filename).write_text(doc["content"], encoding="utf-8")
                payload["documents"].append({
                    "doc_type": doc["doc_type"],
                    "title": doc["title"],
                    "file_url": f"/private-documents/{filename}",
                    "verified": False,
                })
            started = time.perf_counter()
            result = await ai_verifier.verify_campaign_request(
                title=payload["title"],
                category=payload["category"],
                story=payload["story"],
                goal_amount=payload["goal_amount"],
                beneficiary_name=payload.get("beneficiary_name"),
                beneficiary_type=payload.get("beneficiary_type", "SELF"),
                location=f"{payload.get('city', '')}, {payload.get('state', '')}".strip(", "),
                proof_documents=payload["documents"],
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            # Match the campaign submission path: red flags or review/reject recommendations
            # result in FLAGGED; NEEDS_MORE_INFO alone remains pending verification.
            flagged = result.recommendation in {"FLAG_FOR_REVIEW", "REJECT"} or bool(result.red_flags)
            predictions.append({
                "case_id": case["case_id"],
                "ground_truth": case["ground_truth"],
                "scenario_group": case["scenario_group"],
                "category": payload["category"],
                "flagged": flagged,
                "recommendation": result.recommendation,
                "score": result.authenticity_score,
                "red_flag_count": len(result.red_flags),
                "retrieved_evidence_count": len(result.supporting_evidence),
                "model_used": result.model_used,
                "fallback_reason": result.fallback_reason,
                "fraud_positive": case["ground_truth"] == "fraudulent",
                "latency_ms": elapsed_ms,
            })
    return predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-gemini", action="store_true", help="Use configured Gemini embeddings and generation; makes external API calls and may incur charges")
    parser.add_argument("--output-dir", type=Path, help="Write results and predictions to this directory without replacing the saved default reports")
    args = parser.parse_args()
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(cases) != 200 or any(not case.get("synthetic") for case in cases):
        raise SystemExit("Expected exactly 200 explicitly synthetic cases")

    # Offline is the safe default. Live mode must be explicitly selected by the operator.
    if args.live_gemini and not settings.GEMINI_API_KEY:
        raise SystemExit("--live-gemini requires GEMINI_API_KEY in the backend environment")
    if not args.live_gemini:
        settings.GEMINI_API_KEY = ""
        ai_verifier.api_key = ""
    else:
        asyncio.run(gemini_preflight())
    predictions = asyncio.run(evaluate(cases))
    overall = score_metrics(predictions)
    by_truth = {}
    for label in ("legitimate", "fraudulent", "borderline"):
        group = [row for row in predictions if row["ground_truth"] == label]
        by_truth[label] = {"count": len(group), "flagged": sum(row["flagged"] for row in group)}
    by_category = {}
    for category in sorted({row["category"] for row in predictions}):
        by_category[category] = score_metrics([row for row in predictions if row["category"] == category])

    clearly_labeled = [row for row in predictions if row["ground_truth"] in {"legitimate", "fraudulent"}]
    legitimate_rows = [row for row in predictions if row["ground_truth"] == "legitimate"]
    borderline_rows = [row for row in predictions if row["ground_truth"] == "borderline"]
    gemini_rows = [row for row in predictions if row["model_used"] != "crowdfund-india-trust-v1"]
    fallback_rows = [row for row in predictions if row["model_used"] == "crowdfund-india-trust-v1"]
    report = {
        "dataset": DATASET.name,
        "synthetic": True,
        "evaluation_path": ("Gemini attempted with automatic local fallback; use per-case model_used and success/fallback counts" if args.live_gemini else "AIVerifierService local fallback with RAG lexical retrieval; Gemini generation and embeddings disabled"),
        "gemini_successful_cases": len(gemini_rows),
        "gemini_success_cases_by_ground_truth": {label: sum(row["ground_truth"] == label for row in gemini_rows) for label in ("legitimate", "fraudulent", "borderline")},
        "local_fallback_cases": len(fallback_rows),
        "fallback_reason_counts": {
            reason: sum(row["fallback_reason"] == reason for row in fallback_rows)
            for reason in sorted({row["fallback_reason"] for row in fallback_rows if row["fallback_reason"]})
        },
        "gemini_only_success_subset": score_metrics(gemini_rows) if gemini_rows else None,
        "decision_rule": "Flagged when recommendation is FLAG_FOR_REVIEW or REJECT, or red_flags is non-empty; mirrors campaign submission status logic.",
        "binary_mapping": "Fraudulent is positive; legitimate and borderline are negative so flagged borderline cases count as false positives.",
        "overall": overall,
        "clearly_labeled_only_excluding_borderline": score_metrics(clearly_labeled),
        "legitimate_only_false_positive_rate": round(sum(row["flagged"] for row in legitimate_rows) / len(legitimate_rows), 4),
        "borderline_flag_rate": round(sum(row["flagged"] for row in borderline_rows) / len(borderline_rows), 4),
        "by_ground_truth": by_truth,
        "by_category": by_category,
    }
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        results_path = args.output_dir / "results.json"
        predictions_path = args.output_dir / "predictions.csv"
        report["run_id"] = args.output_dir.name
    elif args.live_gemini:
        run_id = datetime.now(timezone.utc).strftime("live_gemini_%Y%m%dT%H%M%SZ")
        run_dir = Path(__file__).with_name("runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        results_path = run_dir / "results.json"
        predictions_path = run_dir / "predictions.csv"
        report["run_id"] = run_id
    else:
        results_path = RESULTS
        predictions_path = PREDICTIONS
    results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with predictions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    print(json.dumps({**report, "results_path": str(results_path), "predictions_path": str(predictions_path)}, indent=2))


if __name__ == "__main__":
    main()
