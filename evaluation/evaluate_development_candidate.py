"""Paired offline evaluation of the unchanged verifier and development candidate."""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.services.ai_verifier import ai_verifier
from app.services.development_verifier import verify_development_case
from app.services.fraud_detector import format_inr
from app.services import rag
from evaluate_fundraising import evaluate as evaluate_baseline

DATASET = Path(__file__).with_name("development_scenarios_v1.jsonl")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_paired(baseline, candidate):
    left = {(row["case_id"], row["ground_truth"]) for row in baseline}
    right = {(row["case_id"], row["ground_truth"]) for row in candidate}
    if left != right or len(left) != len(baseline) or len(right) != len(candidate):
        raise ValueError("Baseline and candidate must contain identical unique case IDs and labels")
    baseline_by_id = {row["case_id"]: row for row in baseline}
    for row in candidate:
        if "retrieved_evidence_count" in baseline_by_id[row["case_id"]] and row.get("retrieved_evidence_count") != baseline_by_id[row["case_id"]]["retrieved_evidence_count"]:
            raise ValueError(f"Baseline and candidate retrieval counts differ for {row['case_id']}")


def build_retrieval_query(data):
    location = f"{data.get('city', '')}, {data.get('state', '')}".strip(", ")
    return " ".join([data["title"], data["category"], data.get("beneficiary_name") or "",
                     location, data["story"], format_inr(data["goal_amount"])])


def binary_metrics(rows):
    positive = lambda row: row["ground_truth"] == "fraudulent"
    flagged = lambda row: bool(row["flagged"])
    tp = sum(positive(r) and flagged(r) for r in rows)
    fp = sum(not positive(r) and flagged(r) for r in rows)
    fn = sum(positive(r) and not flagged(r) for r in rows)
    tn = sum(not positive(r) and not flagged(r) for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    negatives = sum(not positive(r) for r in rows)
    review_n = sum(r.get("recommendation") in {"FLAG_FOR_REVIEW", "NEEDS_MORE_INFO", "REJECT"} for r in rows)
    return {
        "cases": len(rows),
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
        "false_positive_rate": round(fp / negatives, 4) if negatives else None,
        "review_burden_cases": review_n,
        "review_burden_rate": round(review_n / len(rows), 4) if rows else 0.0,
        "manual_review_recommendations": sum(r.get("recommendation") == "FLAG_FOR_REVIEW" for r in rows),
        "needs_more_information": sum(r.get("recommendation") == "NEEDS_MORE_INFO" for r in rows),
        "rejections": sum(r.get("recommendation") == "REJECT" for r in rows),
        "latency_ms": ({
            "mean": round(statistics.mean(r["latency_ms"] for r in rows), 2),
            "median": round(statistics.median(r["latency_ms"] for r in rows), 2),
            "p95": round(sorted(r["latency_ms"] for r in rows)[max(0, math.ceil(.95 * len(rows)) - 1)], 2),
        } if rows and all("latency_ms" in r for r in rows) else None),
    }


def load_cases():
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]
    if len(cases) != 120 or any(not case.get("synthetic") for case in cases):
        raise ValueError("Expected the fixed 120-case synthetic development corpus")
    return cases


def materialize_documents(cases, directory):
    for case in cases:
        payload = case["input"]
        docs = []
        for idx, doc in enumerate(payload.get("documents", []), 1):
            filename = f"{case['case_id'].lower()}-{idx}.txt"
            (directory / filename).write_text(doc["content"], encoding="utf-8")
            docs.append({"doc_type": doc["doc_type"], "title": doc["title"], "file_url": f"/private-documents/{filename}"})
        payload["_retrieval_documents"] = docs


async def evaluate_candidate(cases):
    predictions = []
    with tempfile.TemporaryDirectory(prefix="sevafund-dev-candidate-") as scratch:
        directory = Path(scratch)
        rag.UPLOAD_DIR = directory
        materialize_documents(cases, directory)
        for case in cases:
            data = case["input"]
            started = time.perf_counter()
            query = build_retrieval_query(data)
            retrieved = await rag.retrieve_evidence(data["_retrieval_documents"], query, top_k=5)
            output = verify_development_case(
                data["title"], data["category"], data["story"], data["goal_amount"],
                beneficiary_name=data.get("beneficiary_name"), documents=[item["text"] for item in retrieved],
            )
            elapsed = (time.perf_counter() - started) * 1000
            action = output.result.recommendation
            predictions.append({
                "case_id": case["case_id"], "ground_truth": case["ground_truth"],
                "scenario_family": case["scenario_family"], "document_source": case["document_source"],
                "group_fold": case["group_fold"], "category": data["category"],
                "evidence_relation": output.evidence_relation, "evidence_conflicts": output.evidence_conflicts,
                "retrieved_evidence_count": len(retrieved), "recommendation": action,
                "flagged": action in {"FLAG_FOR_REVIEW", "REJECT"} or bool(output.result.red_flags),
                "fraud_positive": case["ground_truth"] == "fraudulent",
                "score": output.result.authenticity_score, "model_used": output.result.model_used,
                "latency_ms": elapsed,
            })
    return predictions


def normalize_baseline(predictions, cases):
    metadata = {c["case_id"]: c for c in cases}
    out = []
    for row in predictions:
        source = metadata[row["case_id"]]
        out.append({
            **row, "scenario_family": source["scenario_family"],
            "document_source": source["document_source"], "group_fold": source["group_fold"],
            "evidence_relation": source["evidence_relation"],
            "recommendation": row["recommendation"],
        })
    return out


def grouped_metrics(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {name: binary_metrics(group) for name, group in sorted(groups.items())}


async def run(output_dir=None):
    cases = load_cases()
    # Hard disable generation and embeddings regardless of local environment.
    settings.GEMINI_API_KEY = ""
    ai_verifier.api_key = ""
    old_group = [dict(case, scenario_group=case["scenario_family"]) for case in cases]
    baseline = normalize_baseline(await evaluate_baseline(old_group), cases)
    candidate = await evaluate_candidate(cases)
    assert_paired(baseline, candidate)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = output_dir or Path(__file__).with_name("runs") / f"development_candidate_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "baseline.json").write_text(json.dumps({"metrics": binary_metrics(baseline), "predictions": baseline}, indent=2) + "\n", encoding="utf-8")
    (out / "candidate.json").write_text(json.dumps({"metrics": binary_metrics(candidate), "predictions": candidate}, indent=2) + "\n", encoding="utf-8")
    paired = []
    base_by_id = {r["case_id"]: r for r in baseline}
    for row in candidate:
        left = base_by_id[row["case_id"]]
        paired.append({"case_id": row["case_id"], "ground_truth": row["ground_truth"], "scenario_family": row["scenario_family"], "document_source": row["document_source"], "group_fold": row["group_fold"], "category": row["category"], "baseline_recommendation": left["recommendation"], "baseline_flagged": left["flagged"], "candidate_recommendation": row["recommendation"], "candidate_flagged": row["flagged"], "candidate_evidence_relation": row["evidence_relation"], "candidate_evidence_conflicts": "; ".join(row["evidence_conflicts"]), "baseline_latency_ms": left["latency_ms"], "candidate_latency_ms": row["latency_ms"]})
    with (out / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paired[0]))
        writer.writeheader()
        writer.writerows(paired)
    report = {
        "run_id": out.name, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET.name, "dataset_sha256": digest(DATASET), "synthetic": True,
        "cases": len(cases), "labels": dict(Counter(c["ground_truth"] for c in cases)),
        "evaluation_mode": "Offline Python verifier + lexical document retrieval; Gemini generation and embeddings disabled",
        "gemini_calls_made": 0, "paired_case_ids_and_labels_identical": True,
        "fraud_positive_definition": "Only fraudulent is positive; legitimate and borderline are negative for binary metrics.",
        "flag_definition": "FLAG_FOR_REVIEW or REJECT, or any explicit red flag. Review burden includes FLAG_FOR_REVIEW, NEEDS_MORE_INFO, and REJECT.",
        "baseline": binary_metrics(baseline), "candidate": binary_metrics(candidate),
        "baseline_by_category": grouped_metrics(baseline, "category"),
        "candidate_by_category": grouped_metrics(candidate, "category"),
        "candidate_by_class": grouped_metrics(candidate, "ground_truth"),
        "candidate_by_family": grouped_metrics(candidate, "scenario_family"),
        "candidate_by_document_source": grouped_metrics(candidate, "document_source"),
        "candidate_by_group_fold": grouped_metrics(candidate, "group_fold"),
        "reproducibility": {"python": sys.version, "dataset_sha256": digest(DATASET),
                            "baseline_evaluator_sha256": digest(Path(__file__).with_name("evaluate_fundraising.py")),
                            "candidate_sha256": digest(ROOT / "app/services/development_verifier.py"),
                            "generator_sha256": digest(Path(__file__).with_name("generate_development_dataset.py")),
                            "generation_enabled": False, "embeddings_enabled": False,
                            "production_scoring_modified": False,
                            "candidate_decision_policy": "supports=>AUTO_APPROVE; contradictions=>FLAG_FOR_REVIEW; incomplete or unavailable=>NEEDS_MORE_INFO; REJECT requires multiple conflicts plus explicit document-fabrication signal."},
    }
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "run_config.json").write_text(json.dumps(report["reproducibility"], indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": out.name, "results": str(out / "results.json"), "baseline": report["baseline"], "candidate": report["candidate"]}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.output_dir))
