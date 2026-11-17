"""Build final report/CSV from persisted predictions without executing a verifier."""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import evaluate_final_test_v3 as runner
from evaluation.evaluate_development_verifier_v3 import aggregate, binary_metrics
from evaluation.verify_candidate_v3_freeze import verify as verify_freeze


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    status = verify_freeze()
    if not status["valid"]:
        raise SystemExit("Frozen engine verification failed; refusing to finalize")
    dataset_hash = sha(runner.DATASET)
    run_dir = ROOT / "evaluation/runs" / f"final_test_v3_{dataset_hash[:12]}"
    results_path = run_dir / "results.json"
    metadata_path = run_dir / "metadata.json"
    report_path = run_dir / "report.md"
    csv_path = run_dir / "case_level_predictions.csv"
    if report_path.exists():
        raise SystemExit("Final report already exists; refusing to rewrite the finalized result")
    if not results_path.exists() or not metadata_path.exists():
        raise SystemExit("Persisted paired predictions are missing; no verifier will be rerun")

    result_doc = json.loads(results_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("final_dataset_sha256") != dataset_hash:
        raise SystemExit("Persisted results do not match the final corpus hash")
    paired = result_doc["paired_case_level"]
    if set(paired) != {"V2_original", "V3_frozen"}:
        raise SystemExit("Expected persisted V2 and V3 predictions")
    expected_ids = [(row["case_id"], row["ground_truth"]) for row in paired["V2_original"]]
    if len(expected_ids) != 300 or expected_ids != [
            (row["case_id"], row["ground_truth"]) for row in paired["V3_frozen"]]:
        raise SystemExit("Persisted paired predictions are incomplete or misaligned")

    metrics = {name: binary_metrics(rows) for name, rows in paired.items()}
    category_metrics = {name: aggregate(rows, "category") for name, rows in paired.items()}
    failures = {name: runner.target_errors(rows) for name, rows in paired.items()}
    result_doc.update({"metrics": metrics, "category_metrics": category_metrics,
                       "failure_analysis": failures,
                       "execution_audit": {
                           "verifier_executions_started": 2,
                           "completed_paired_evaluations": 1,
                           "first_attempt": "Stopped on missing split metadata after one V2 case; no output persisted.",
                           "second_attempt": "All 300 V2 and 300 V3 predictions persisted; CSV export then failed on omitted columns.",
                           "recovery": "Metrics, CSV and report derived from persisted predictions; no verifier was called during recovery.",
                       }})

    fields = ["engine", "split", "case_id", "ground_truth", "category", "scenario_family", "document_source",
              "decision", "predicted_bucket", "authenticity_score", "finding_codes", "critical_missing",
              "optional_missing", "information_request_count", "information_requests", "decision_explanation",
              "runtime_error_count", "errors", "latency_ms"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, rows in paired.items():
            for row in rows:
                writer.writerow({"engine": name, **row,
                                 "finding_codes": ";".join(row["finding_codes"]),
                                 "critical_missing": ";".join(row["critical_missing"]),
                                 "optional_missing": ";".join(row["optional_missing"]),
                                 "information_requests": " | ".join(row["information_requests"]),
                                 "errors": ";".join(row["errors"])})

    runner.aggregate_rows = category_metrics
    report = runner.render_report(metrics, failures, metadata)
    report += ("\n## Execution audit\n\n"
               "The first runner attempt stopped before a paired evaluation completed. A second attempt completed and persisted all predictions, "
               "then failed while exporting CSV because two serializer fields were omitted. The CSV and this report were recovered from the "
               "persisted case predictions; V2 and V3 were not called again. See `metadata.json` and `results.json` for the attempt record.\n")

    metadata["runner_sha256"] = sha(Path(__file__).with_name("evaluate_final_test_v3.py"))
    metadata["finalizer_sha256"] = sha(Path(__file__))
    metadata["execution_count"] = 2
    metadata["completed_paired_evaluations"] = 1
    metadata["result_finalization"] = "Derived metrics, CSV and report from persisted paired predictions; no verifier execution."
    metadata["attempt_history"] = [
        {"attempt": 1, "status": "aborted_before_pair_completion",
         "error": "KeyError: 'split' in shared case serializer",
         "effect": "One V2 case evaluated; no predictions persisted."},
        {"attempt": 2, "status": "paired_predictions_persisted_export_failed",
         "error": "ValueError: CSV fields omitted split and information_request_count",
         "effect": "All 300 V2 and 300 V3 case predictions persisted; CSV/report recovery followed without verifier calls."},
        {"attempt": 3, "status": "artifacts_finalized_from_saved_predictions",
         "effect": "Recomputed aggregate metrics and wrote complete CSV/report without running either engine."},
    ]
    metadata["commands"] = ["./.venv/bin/python -B evaluation/verify_candidate_v3_freeze.py",
                            "./.venv/bin/python -B evaluation/evaluate_final_test_v3.py",
                            "./.venv/bin/python -B evaluation/finalize_final_test_v3.py"]
    results_path.write_text(json.dumps(result_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "cases_per_engine": 300,
                      "metrics": metrics, "category_metrics": category_metrics,
                      "csv_rows": 600, "verifier_rerun_during_finalization": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
