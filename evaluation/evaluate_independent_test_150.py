"""Paired, pre-registered offline evaluation of the frozen SevaFund engines."""
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
from app.schemas.ai import VerificationResult
from app.services.ai_verifier import ai_verifier
from app.services.development_verifier import verify_development_case
from app.services.fraud_detector import format_inr
from app.services import rag
from evaluate_fundraising import evaluate as evaluate_baseline

DATASET = Path(__file__).with_name("independent_test_150.jsonl")
FROZEN_HASHES = {
    "candidate": "f6bba947d5ec1202502ece19e02fdf24b93cdb623a12a59d6eced670118e4eec",
    "baseline_verifier": "3a3b857c8bf658d1400b1a9c92eb1f19a60a405e17ba86199be7298bcd1bc9c8",
    "fraud_rules": "f47e641743d1d66272cf36d6bfa2053245bbf2b68bf15b19075fab41cf97279f",
    "rag": "95b14980be44fd6b658cd4025a0c24a90447a53fb212f42cede257b2f4f71309",
    "config": "edb58aa33fb33fd2dee8dea167b851f524ac1338f0560b13006b6928723d4bb3",
    "schema": "8384f9a64fc3c3fb407409366606fc796adcce5257a02c33de03a7512a962317",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_frozen():
    paths = {
        "candidate": ROOT / "app/services/development_verifier.py",
        "baseline_verifier": ROOT / "app/services/ai_verifier.py",
        "fraud_rules": ROOT / "app/services/fraud_detector.py",
        "rag": ROOT / "app/services/rag.py",
        "config": ROOT / "app/config.py",
        "schema": ROOT / "app/schemas/ai.py",
    }
    actual = {name: digest(path) for name, path in paths.items()}
    if actual != FROZEN_HASHES:
        raise RuntimeError("A frozen verification component changed; evaluation stopped before cases were processed")
    return actual


def assert_paired(baseline, candidate):
    base = {(r["case_id"], r["ground_truth"]) for r in baseline}
    cand = {(r["case_id"], r["ground_truth"]) for r in candidate}
    if base != cand or len(base) != len(baseline) or len(cand) != len(candidate):
        raise ValueError("Baseline and candidate must have identical unique IDs and labels")
    base_by_id = {r["case_id"]: r for r in baseline}
    for row in candidate:
        if row.get("retrieved_evidence_count") != base_by_id[row["case_id"]].get("retrieved_evidence_count"):
            raise ValueError(f"Retrieval count differs for {row['case_id']}")


def score_rows(rows):
    fraud = lambda r: r["ground_truth"] == "fraudulent"
    is_flagged = lambda r: bool(r["flagged"])
    tp = sum(fraud(r) and is_flagged(r) for r in rows)
    fp = sum(not fraud(r) and is_flagged(r) for r in rows)
    fn = sum(fraud(r) and not is_flagged(r) for r in rows)
    tn = sum(not fraud(r) and not is_flagged(r) for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    actions = Counter(r["recommendation"] for r in rows)
    n = len(rows)
    pct = lambda value: round(value / n, 4) if n else None
    latencies = [r["latency_ms"] for r in rows if "latency_ms" in r]
    return {
        "cases": n,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn},
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else None,
        "manual_review_count": actions["FLAG_FOR_REVIEW"], "manual_review_rate": pct(actions["FLAG_FOR_REVIEW"]),
        "needs_more_information_count": actions["NEEDS_MORE_INFO"], "needs_more_information_rate": pct(actions["NEEDS_MORE_INFO"]),
        "rejection_count": actions["REJECT"], "rejection_rate": pct(actions["REJECT"]),
        "system_error_count": actions["SYSTEM_ERROR"], "system_error_rate": pct(actions["SYSTEM_ERROR"]),
        "auto_approval_count": actions["AUTO_APPROVE"], "auto_approval_rate": pct(actions["AUTO_APPROVE"]),
        "total_followup_count": sum(actions[a] for a in ("FLAG_FOR_REVIEW", "NEEDS_MORE_INFO", "REJECT")),
        "total_followup_rate": pct(sum(actions[a] for a in ("FLAG_FOR_REVIEW", "NEEDS_MORE_INFO", "REJECT"))),
        "latency_ms": ({"mean": round(statistics.mean(latencies), 2), "median": round(statistics.median(latencies), 2),
                        "p95": round(sorted(latencies)[max(0, math.ceil(.95 * len(latencies)) - 1)], 2)} if latencies else None),
    }


def grouped(rows, field):
    result = defaultdict(list)
    for row in rows:
        result[row[field]].append(row)
    return {key: score_rows(group) for key, group in sorted(result.items())}


def retrieval_query(data):
    location = f"{data.get('city', '')}, {data.get('state', '')}".strip(", ")
    return " ".join([data["title"], data["category"], data.get("beneficiary_name") or "", location,
                     data["story"], format_inr(data["goal_amount"])])


def materialize(cases, directory):
    for case in cases:
        payload = case["input"]
        references = []
        for i, doc in enumerate(payload.get("documents", []), start=1):
            filename = f"{case['case_id'].lower()}-{i}.txt"
            (directory / filename).write_text(doc["content"], encoding="utf-8")
            references.append({"doc_type": doc["doc_type"], "title": doc["title"], "file_url": f"/private-documents/{filename}"})
        payload["_retrieval_documents"] = references


async def evaluate_candidate(cases):
    predictions = []
    with tempfile.TemporaryDirectory(prefix="sevafund-independent-150-") as scratch:
        root = Path(scratch)
        rag.UPLOAD_DIR = root
        materialize(cases, root)
        for case in cases:
            data = case["input"]
            started = time.perf_counter()
            retrieved = await rag.retrieve_evidence(data["_retrieval_documents"], retrieval_query(data), top_k=5)
            try:
                output = verify_development_case(data["title"], data["category"], data["story"], data["goal_amount"],
                                                 beneficiary_name=data.get("beneficiary_name"),
                                                 documents=[chunk["text"] for chunk in retrieved])
                action = output.result.recommendation
                relation = output.evidence_relation
                conflicts = output.evidence_conflicts
                score = output.result.authenticity_score
                red_flags = output.result.red_flags
                error_category = None
                error_type = None
            except Exception as exc:
                # Record the frozen candidate failure; never turn an exception into a fraud flag.
                action = "SYSTEM_ERROR"
                relation = "unavailable_due_to_error"
                conflicts = []
                score = None
                red_flags = []
                error_type = type(exc).__name__
                error_category = "AMOUNT_PARSE" if isinstance(exc, ValueError) and "invalid literal for int()" in str(exc) else "UNEXPECTED_VERIFIER_ERROR"
            elapsed = (time.perf_counter() - started) * 1000
            predictions.append({
                "case_id": case["case_id"], "ground_truth": case["ground_truth"],
                "scenario_family": case["scenario_family"], "document_source": case["document_source"],
                "category": data["category"], "evidence_design": case["evidence_design"],
                "recommendation": action,
                "flagged": action in {"FLAG_FOR_REVIEW", "REJECT"} or bool(red_flags),
                "fraud_positive": case["ground_truth"] == "fraudulent",
                "retrieved_evidence_count": len(retrieved), "candidate_evidence_relation": relation,
                "candidate_conflicts": conflicts, "score": score,
                "latency_ms": elapsed, "model_used": "sevafund-development-candidate-v1",
                "system_error_category": error_category, "system_error_type": error_type,
            })
    return predictions


def normalize_baseline(rows, cases):
    source = {case["case_id"]: case for case in cases}
    out = []
    for row in rows:
        case = source[row["case_id"]]
        out.append({**row, "scenario_family": case["scenario_family"], "document_source": case["document_source"],
                    "evidence_design": case["evidence_design"]})
    return out


def load_dataset():
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts = Counter(row["ground_truth"] for row in cases)
    categories = Counter(row["input"]["category"] for row in cases)
    if len(cases) != 150 or counts != {"legitimate": 60, "fraudulent": 60, "borderline": 30}:
        raise ValueError(f"Unexpected dataset size/labels: {len(cases)}, {dict(counts)}")
    if categories != {"MEDICAL": 50, "EDUCATION": 50, "COMMUNITY": 50}:
        raise ValueError(f"Unexpected category distribution: {dict(categories)}")
    return cases


async def run(output_dir=None):
    frozen_hashes = assert_frozen()
    cases = load_dataset()
    # This mutates only process-local configuration for the offline run.
    settings.GEMINI_API_KEY = ""
    ai_verifier.api_key = ""
    baseline_cases = [dict(case, scenario_group=case["scenario_family"]) for case in cases]
    baseline = normalize_baseline(await evaluate_baseline(baseline_cases), cases)
    candidate = await evaluate_candidate(cases)
    assert_paired(baseline, candidate)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output_dir or Path(__file__).with_name("runs") / f"independent_test_150_{stamp}"
    target.mkdir(parents=True, exist_ok=False)

    base_metrics, candidate_metrics = score_rows(baseline), score_rows(candidate)
    for name, rows, metrics in (("baseline", baseline, base_metrics), ("candidate", candidate, candidate_metrics)):
        (target / f"{name}.json").write_text(json.dumps({"metrics": metrics, "predictions": rows}, indent=2) + "\n", encoding="utf-8")
    base_by_id = {row["case_id"]: row for row in baseline}
    with (target / "paired_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["case_id", "ground_truth", "category", "scenario_family", "document_source",
                  "baseline_recommendation", "baseline_flagged", "candidate_recommendation", "candidate_flagged",
                  "candidate_evidence_relation", "candidate_conflicts", "retrieved_evidence_count",
                  "baseline_latency_ms", "candidate_latency_ms"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in candidate:
            base = base_by_id[row["case_id"]]
            writer.writerow({"case_id": row["case_id"], "ground_truth": row["ground_truth"], "category": row["category"],
                             "scenario_family": row["scenario_family"], "document_source": row["document_source"],
                             "baseline_recommendation": base["recommendation"], "baseline_flagged": base["flagged"],
                             "candidate_recommendation": row["recommendation"], "candidate_flagged": row["flagged"],
                             "candidate_evidence_relation": row["candidate_evidence_relation"],
                             "candidate_conflicts": "; ".join(row["candidate_conflicts"]),
                             "retrieved_evidence_count": row["retrieved_evidence_count"],
                             "baseline_latency_ms": base["latency_ms"], "candidate_latency_ms": row["latency_ms"]})

    report = {
        "run_id": target.name, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET.name, "dataset_sha256": digest(DATASET), "synthetic": True,
        "case_count": len(cases), "label_counts": dict(Counter(r["ground_truth"] for r in cases)),
        "category_counts": dict(Counter(r["input"]["category"] for r in cases)),
        "evaluation_mode": "Offline Python + lexical retrieval; Gemini generation and embeddings disabled",
        "gemini_calls_made": 0, "paired_ids_labels_and_retrieval_counts_match": True,
        "fraud_detection_definition": "Only FLAG_FOR_REVIEW/REJECT or an emitted red flag counts as fraud-detected; NEEDS_MORE_INFO alone is not a positive fraud prediction.",
        "review_definition": "Manual review rate counts FLAG_FOR_REVIEW only; follow-up burden additionally counts NEEDS_MORE_INFO and REJECT.",
        "baseline": base_metrics, "candidate": candidate_metrics,
        "baseline_by_category": grouped(baseline, "category"), "candidate_by_category": grouped(candidate, "category"),
        "baseline_by_class": grouped(baseline, "ground_truth"), "candidate_by_class": grouped(candidate, "ground_truth"),
        "candidate_by_family": grouped(candidate, "scenario_family"),
        "frozen_engine_hashes": frozen_hashes,
        "reproducibility": {"python": sys.version, "dataset_sha256": digest(DATASET),
                            "protocol_sha256": digest(Path(__file__).with_name("independent_test_150_protocol.md")),
                            "generator_sha256": digest(Path(__file__).with_name("generate_independent_test_150.py")),
                            "evaluator_sha256": digest(Path(__file__)), "generation_enabled": False,
                            "embeddings_enabled": False, "candidate_or_baseline_modified_after_results": False},
        "interpretation": "Independent synthetic test only. Offline lexical retrieval results are not Gemini or semantic RAG performance.",
    }
    (target / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (target / "run_config.json").write_text(json.dumps(report["reproducibility"], indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": target.name, "results_path": str(target / "results.json"),
                      "baseline": base_metrics, "candidate": candidate_metrics}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.output_dir))
