"""Run the frozen V2/V3 engines once on the post-freeze synthetic final set."""
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.development_verifier_v3 import Decision, ENGINE_VERSION
from evaluation.evaluate_development_verifier_v3 import binary_metrics, run_engine, aggregate
from evaluation.verify_candidate_v3_freeze import verify as verify_freeze

DATASET = ROOT / "evaluation/final_test_scenarios_v3.jsonl"
DEVELOPMENT = ROOT / "evaluation/development_scenarios_v3.jsonl"
MANIFEST = ROOT / "evaluation/development_candidate_v3_freeze.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_final_cases():
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 300:
        raise ValueError(f"Final corpus must contain 300 scenarios, found {len(rows)}")
    if Counter(row["ground_truth"] for row in rows) != Counter({"legitimate": 100, "fraudulent": 100, "borderline": 100}):
        raise ValueError("Final label counts differ from the frozen protocol")
    if Counter(row["input"]["category"] for row in rows) != Counter({"MEDICAL": 100, "EDUCATION": 100, "COMMUNITY": 100}):
        raise ValueError("Final category counts differ from the protocol")
    development = [json.loads(line) for line in DEVELOPMENT.read_text(encoding="utf-8").splitlines() if line.strip()]
    prior_families = {row["scenario_family"] for row in development}
    if prior_families.intersection(row["scenario_family"] for row in rows):
        raise ValueError("A final-test family appears in V3 development data")
    ids = [row["case_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate final case IDs")
    family = {}
    for row in rows:
        key = row["scenario_family"]
        family.setdefault(key, {"labels": set(), "sources": set(), "count": 0})
        family[key]["labels"].add(row["ground_truth"])
        family[key]["sources"].add(row["document_source"])
        family[key]["count"] += 1
    if len(family) != 30 or any(len(v["labels"]) != 1 or len(v["sources"]) != 1 or v["count"] != 10
                                for v in family.values()):
        raise ValueError("Expected 30 family/source groups with ten cases and one label each")
    if not all(row.get("synthetic") is True and row.get("label_basis") for row in rows):
        raise ValueError("All final records must disclose synthetic authorship and label basis")
    return rows


def cell_count(rows, predicate):
    return sum(1 for row in rows if predicate(row))


def class_matrix(rows):
    labels = ("legitimate", "fraudulent", "borderline")
    buckets = ("legitimate", "fraudulent", "unresolved")
    return {label: {bucket: cell_count(rows, lambda r: r["ground_truth"] == label and r["predicted_bucket"] == bucket)
                    for bucket in buckets} for label in labels}


def target_errors(rows):
    return {
        "fraudulent_auto_approvals": [{"case_id": r["case_id"], "family": r["scenario_family"],
                                       "category": r["category"], "finding_codes": r["finding_codes"],
                                       "critical_missing": r["critical_missing"]}
                                      for r in rows if r["ground_truth"] == "fraudulent" and r["decision"] == "APPROVED"],
        "legitimate_flagged_or_rejected": [{"case_id": r["case_id"], "family": r["scenario_family"],
                                            "category": r["category"], "decision": r["decision"],
                                            "finding_codes": r["finding_codes"]}
                                           for r in rows if r["ground_truth"] == "legitimate"
                                           and r["decision"] in ("FLAG_FOR_REVIEW", "REJECTED")],
        "runtime_error_cases": [{"case_id": r["case_id"], "errors": r["errors"]}
                                for r in rows if r["decision"] == "VERIFICATION_ERROR"],
    }


def pct(value):
    return "—" if value is None else f"{value * 100:.1f}%"


def render_report(metrics, failures, metadata):
    lines = ["# SevaFund V3 synthetic final evaluation", "",
             "**One-time offline run on a new, synthetic 300-case corpus.** No Gemini calls, embeddings, semantic RAG, or issuer verification were used.",
             "Primary binary metrics exclude borderline cases. Labels were authored in the project workflow; independent authorship and human adjudication were unavailable.", "",
             "## V2 versus frozen V3", "",
             "| Engine | N | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Reject | Runtime errors | Mean / p50 / p95 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, m in metrics.items():
        lat = m["latency_ms"]
        lines.append(f"| {name} | {m['n_total']} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | {pct(m['false_positive_rate'])} | "
                     f"{m['fraudulent_auto_approved']} ({pct(m['fraudulent_auto_approval_rate'])}) | "
                     f"{m['legitimate_auto_approved']} ({pct(m['legitimate_auto_approval_rate'])}) | {pct(m['manual_review_rate'])} | "
                     f"{pct(m['information_request_rate'])} | {pct(m['rejection_rate'])} | {pct(m['runtime_error_rate'])} | "
                     f"{lat['mean']:.2f} / {lat['p50']:.2f} / {lat['p95']:.2f} |")
    for name, m in metrics.items():
        cm = m["binary_confusion_matrix"]
        lines.extend(["", f"## {name} confusion matrices", "",
                      "Binary fraud-vs-legitimate (borderline excluded):", "",
                      "| | Predicted fraud/review | Predicted approved |", "|---|---:|---:|",
                      f"| Actual fraudulent | {cm['TP']} | {cm['FN']} |",
                      f"| Actual legitimate | {cm['FP']} | {cm['TN']} |", "",
                      "Three-class disposition:", "",
                      "| Actual \\ Predicted | Approved | Flag/reject | Needs info/error |", "|---|---:|---:|---:|"])
        for label, row in m["three_class_disposition_matrix"].items():
            lines.append(f"| {label} | {row['legitimate']} | {row['fraudulent']} | {row['unresolved']} |")
        lines.extend(["", "Category-wise results:", "",
                      "| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for category, c in aggregate_rows[name].items():
            lines.append(f"| {category} | {c['n_total']} | {pct(c['precision'])} | {pct(c['recall'])} | {pct(c['f1'])} | "
                         f"{pct(c['false_positive_rate'])} | {pct(c['manual_review_rate'])} | {pct(c['information_request_rate'])} |")
    lines.extend(["", "## Fraud auto-approval analysis", "",
                  "Cases listed here were labeled fraudulent before verifier execution but received APPROVED. For the `consistent_fabrication` family, this is an expected limit: its visible documents agree, while the author-only provenance is not available to an offline verifier.", ""])
    for name, data in failures.items():
        cases = data["fraudulent_auto_approvals"]
        lines.append(f"**{name}: {len(cases)} fraudulent auto-approvals** — " +
                     (", ".join(f"{x['case_id']} ({x['family']})" for x in cases) or "none") + ".")
    lines.extend(["", "## Limitation and evidence status", "",
                  "- The cases and supporting documents are synthetic; one project agent authored them and assigned their labels. No independent author or human adjudicator validated the labels.",
                  "- The run is not a real-world accuracy estimate. The synthetic design contains repeated family-level structures even though those families are new relative to development data.",
                  "- A coherent fabricated dossier cannot be authenticated from internal consistency alone. Independent hospital, school, supplier, registry, beneficiary identity and platform payout checks are necessary before funds are released.",
                  "- Borderline campaigns are reported as unresolved/review/approval dispositions and are excluded from binary fraud metrics.",
                  "- This is offline heuristic/full-text verification, not Gemini, embeddings, or semantic RAG.",
                  "- V3 package SHA-256: `" + metadata["v3_package_sha256"] + "`.",
                  "- Final dataset SHA-256: `" + metadata["final_dataset_sha256"] + "`.",
                  "- Frozen configuration SHA-256: `" + metadata["config_sha256"] + "`.",
                  "- No V2 or V3 engine code was modified after this run."])
    return "\n".join(lines) + "\n"


aggregate_rows = {}


def main():
    freeze_status = verify_freeze()
    if not freeze_status["valid"]:
        raise SystemExit("V3 freeze check failed; refusing final evaluation")
    if not DATASET.exists():
        raise SystemExit("Generate the post-freeze final corpus first")
    cases = load_final_cases()
    # The final corpus is intentionally not split into development partitions;
    # the shared serializer expects a split label, so attach a run-only value.
    for row in cases:
        row.setdefault("split", "final_test")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dataset_hash = sha(DATASET)
    run_dir = ROOT / "evaluation/runs" / f"final_test_v3_{dataset_hash[:12]}"
    # Reserve the one-run record before model execution. The initial attempt
    # aborted on a serializer KeyError after the first V2 case and persisted no
    # predictions; permit only that empty reservation to be reused and record it.
    prior_attempts = []
    if run_dir.exists():
        if any(run_dir.iterdir()):
            raise SystemExit(f"Final evaluation already has artifacts at {run_dir}; refusing to rerun")
        prior_attempts.append({
            "attempt": 1,
            "status": "aborted_before_pair_completion",
            "error": "KeyError: 'split' in shared case serializer",
            "effect": "One V2 case was evaluated before serialization failed; no predictions were persisted.",
        })
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
    paired = {
        "V2_original": run_engine(cases, "v2"),
        "V3_frozen": run_engine(cases, "v3"),
    }
    expected = [(row["case_id"], row["ground_truth"]) for row in cases]
    for name, rows in paired.items():
        if [(row["case_id"], row["ground_truth"]) for row in rows] != expected:
            raise AssertionError(f"Case/label pairing changed in {name}")
    metrics = {name: binary_metrics(rows) for name, rows in paired.items()}
    global aggregate_rows
    aggregate_rows = {name: aggregate(rows, "category") for name, rows in paired.items()}
    failures = {name: target_errors(rows) for name, rows in paired.items()}
    metadata = {
        "final_dataset": str(DATASET.relative_to(ROOT)), "final_dataset_sha256": dataset_hash,
        "final_dataset_rows": len(cases), "scenario_families": len({r["scenario_family"] for r in cases}),
        "synthetic": True, "authorship": "single project author; no independent authorship or human adjudication",
        "frozen_engine_version": ENGINE_VERSION, "v3_package_sha256": manifest["v3_package"]["combined"],
        "v2_package_sha256": manifest["v2_package"]["combined"],
        "config_sha256": manifest["config_sha256"], "config_digest": manifest["config_digest"],
        "v3_freeze_manifest_sha256": sha(MANIFEST),
        "generator_sha256": sha(Path(__file__).with_name("generate_final_test_v3.py")),
        "runner_sha256": sha(Path(__file__)), "python": sys.version.split()[0],
        "dependencies": {name: importlib.metadata.version(name) for name in ("pydantic", "pytest")},
        "api_calls": 0, "rag": "none; offline full document text",
        "execution_count": len(prior_attempts) + 1,
        "attempt_history": prior_attempts + [{
            "attempt": len(prior_attempts) + 1, "status": "completed",
            "effect": "Paired V2/V3 evaluation completed on all 300 identical case IDs and labels.",
        }],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "commands": ["./.venv/bin/python -B evaluation/verify_candidate_v3_freeze.py",
                     "./.venv/bin/python -B evaluation/evaluate_final_test_v3.py"],
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps({"metrics": metrics, "category_metrics": aggregate_rows,
                                                        "paired_case_level": paired,
                                                        "failure_analysis": failures}, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8")
    with (run_dir / "case_level_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["engine", "split", "case_id", "ground_truth", "category", "scenario_family", "document_source",
                  "decision", "predicted_bucket", "authenticity_score", "finding_codes", "critical_missing",
                  "optional_missing", "information_request_count", "information_requests", "decision_explanation",
                  "runtime_error_count", "errors", "latency_ms"]
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
    (run_dir / "report.md").write_text(render_report(metrics, failures, metadata), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "metadata": metadata, "metrics": metrics,
                      "category_metrics": aggregate_rows, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
