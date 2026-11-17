"""Evaluate the independent 100-case benchmark with the existing offline engine."""
import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = Path(__file__).resolve().parent
DATASET = EVALUATION_DIR / "independent_benchmark_100.jsonl"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVALUATION_DIR))

from app.config import settings
from app.services.ai_verifier import ai_verifier
from app.services.fraud_detector import RED_FLAG_PATTERNS
from evaluate_fundraising import evaluate, score_metrics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def class_rates(rows):
    result = {}
    for label in ("legitimate", "fraudulent", "borderline"):
        group = [row for row in rows if row["ground_truth"] == label]
        n = len(group)
        result[label] = {
            "cases": n,
            "any_flagged": sum(row["flagged"] for row in group),
            "any_flag_rate": round(sum(row["flagged"] for row in group) / n, 4) if n else None,
            "review_recommendations": sum(row["recommendation"] == "FLAG_FOR_REVIEW" for row in group),
            "review_recommendation_rate": round(sum(row["recommendation"] == "FLAG_FOR_REVIEW" for row in group) / n, 4) if n else None,
            "rejections": sum(row["recommendation"] == "REJECT" for row in group),
            "rejection_rate": round(sum(row["recommendation"] == "REJECT" for row in group) / n, 4) if n else None,
            "red_flag_matches": sum(bool(row["red_flag_count"]) for row in group),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="New directory for results; existing outputs are never overwritten")
    args = parser.parse_args()

    scenarios = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts = Counter(row["ground_truth"] for row in scenarios)
    if len(scenarios) != 100 or counts != {"legitimate": 40, "fraudulent": 40, "borderline": 20}:
        raise SystemExit(f"Unexpected benchmark size or labels: n={len(scenarios)}, counts={dict(counts)}")
    if len({row["case_id"] for row in scenarios}) != 100 or any(not row.get("synthetic") for row in scenarios):
        raise SystemExit("Benchmark case IDs must be unique and every case explicitly synthetic")

    # Explicitly disable Gemini; reuse the existing lexical retrieval and local
    # heuristic path without changing its scoring or thresholds.
    settings.GEMINI_API_KEY = ""
    ai_verifier.api_key = ""
    predictions = asyncio.run(evaluate(scenarios))
    overall = score_metrics(predictions)
    group_rates = class_rates(predictions)

    old_dataset = EVALUATION_DIR / "fundraising_scenarios.jsonl"
    old_stories = {
        json.loads(line)["input"]["story"].casefold()
        for line in old_dataset.read_text(encoding="utf-8").splitlines() if line.strip()
    }
    exact_story_duplicates = sum(row["input"]["story"].casefold() in old_stories for row in scenarios)
    regex_matches = []
    for row in scenarios:
        text = row["input"]["title"] + "\n" + row["input"]["story"]
        if any(re.search(pattern, text, re.IGNORECASE) for pattern, _, _ in RED_FLAG_PATTERNS):
            regex_matches.append(row["case_id"])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or EVALUATION_DIR / "runs" / f"independent_benchmark_100_offline_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "run_id": output_dir.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET.name,
        "synthetic": True,
        "configuration": "Python heuristics + lexical retrieval; Gemini generation and embeddings disabled",
        "gemini_calls_made": 0,
        "labels": {"fraudulent": "positive", "legitimate_and_borderline": "negative"},
        "decision_rule": "Any flag when recommendation is FLAG_FOR_REVIEW or REJECT, or red_flags is non-empty; exact review and reject actions are reported separately.",
        "overall": overall,
        "class_wise_rates": group_rates,
        "by_category": {
            category: score_metrics([row for row in predictions if row["category"] == category])
            for category in sorted({row["category"] for row in predictions})
        },
        "novelty_checks": {
            "exact_old_story_duplicates": exact_story_duplicates,
            "existing_red_flag_regex_matching_cases": regex_matches,
            "case_ids_unique": True,
            "narratives_unique": len({row["input"]["story"] for row in scenarios}) == 100,
        },
        "interpretation": "Offline-only synthetic benchmark result; not Gemini or semantic-embedding RAG performance.",
    }
    config = {
        "command": f".venv/bin/python -B evaluation/evaluate_independent_benchmark_100.py --output-dir {output_dir}",
        "python_version": sys.version,
        "dataset_sha256": digest(DATASET),
        "prior_200_case_dataset_sha256": digest(old_dataset),
        "evaluator_sha256": digest(Path(__file__)),
        "shared_offline_evaluator_sha256": digest(EVALUATION_DIR / "evaluate_fundraising.py"),
        "ai_verifier_sha256": digest(ROOT / "app/services/ai_verifier.py"),
        "fraud_detector_sha256": digest(ROOT / "app/services/fraud_detector.py"),
        "rag_sha256": digest(ROOT / "app/services/rag.py"),
        "dataset_counts": dict(counts),
        "generation_enabled": False,
        "embeddings_enabled": False,
        "scoring_logic_or_thresholds_changed": False,
    }
    (output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "run_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    print(json.dumps({**report, "results_path": str(output_dir / "results.json"), "predictions_path": str(output_dir / "predictions.csv"), "run_config_path": str(output_dir / "run_config.json")}, indent=2))


if __name__ == "__main__":
    main()
