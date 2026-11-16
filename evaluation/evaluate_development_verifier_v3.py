"""Paired local-only V2/V3 development evaluation and feature ablations."""
import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import statistics
import sys
import time
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.development_verifier_v2 import CaseInput as CaseV2, DocumentInput as DocumentV2, verify_case as verify_v2
from app.services.development_verifier_v2.config import DEFAULT_CONFIG as DEFAULT_V2_CONFIG
from app.services.development_verifier_v3 import (CaseInput as CaseV3, Decision as DecisionV3,
    DocumentInput as DocumentV3, VerifierConfig, verify_case as verify_v3)
from app.services.development_verifier_v3.config import DEFAULT_CONFIG

DATASET = ROOT / "evaluation" / "development_scenarios_v3.jsonl"
RUNS = ROOT / "evaluation" / "runs"
DECISIONS = ("APPROVED", "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW", "REJECTED", "VERIFICATION_ERROR")
ABLATIONS = {
    "full_v3": DEFAULT_CONFIG,
    "without_category_awareness": VerifierConfig(enable_category=False),
    "without_cross_document_checks": VerifierConfig(enable_cross_document=False),
    "without_improved_financial_parsing": VerifierConfig(enable_financial_parsing=False),
    "without_tiered_evidence_requirements": VerifierConfig(enable_evidence_tiers=False),
    "without_uncertainty_policy": VerifierConfig(enable_uncertainty_policy=False),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases():
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 180:
        raise ValueError(f"Expected 180 V3 development cases; found {len(rows)}")
    labels = Counter(row["ground_truth"] for row in rows)
    if labels != {"legitimate": 60, "fraudulent": 60, "borderline": 60}:
        raise ValueError(f"Unexpected labels: {dict(labels)}")
    family_splits = defaultdict(set)
    for row in rows:
        family_splits[row["scenario_family"]].add(row["split"])
    if any(len(splits) > 1 for splits in family_splits.values()):
        raise ValueError("A scenario family crosses development/validation splits")
    return rows


def v2_input(data):
    docs = [DocumentV2(title=doc["title"], doc_type=doc["doc_type"], text=doc.get("content", ""))
            for doc in data.get("documents", [])]
    submitted = date.fromisoformat(data["submitted_on"]) if data.get("submitted_on") else None
    return CaseV2(title=data["title"], category=data["category"], story=data["story"],
                  goal_amount=data["goal_amount"], beneficiary_name=data.get("beneficiary_name"),
                  beneficiary_type=data.get("beneficiary_type"), city=data.get("city"), state=data.get("state"),
                  submitted_on=submitted, documents=docs)


def v3_input(data):
    docs = [DocumentV3(title=doc["title"], doc_type=doc["doc_type"], text=doc.get("content", ""))
            for doc in data.get("documents", [])]
    submitted = date.fromisoformat(data["submitted_on"]) if data.get("submitted_on") else None
    return CaseV3(title=data["title"], category=data["category"], story=data["story"],
                  goal_amount=data["goal_amount"], goal_currency=data.get("goal_currency", "INR"),
                  beneficiary_name=data.get("beneficiary_name"), beneficiary_type=data.get("beneficiary_type"),
                  city=data.get("city"), state=data.get("state"), submitted_on=submitted, documents=docs)


def prediction_bucket(decision):
    if decision == "APPROVED":
        return "legitimate"
    if decision in ("FLAG_FOR_REVIEW", "REJECTED"):
        return "fraudulent"
    return "unresolved"


def binary_metrics(rows):
    # Primary fraud metrics use only adjudicable legitimate/fraudulent labels.
    adjudicable = [r for r in rows if r["ground_truth"] in ("legitimate", "fraudulent")]
    fraud = [r for r in adjudicable if r["ground_truth"] == "fraudulent"]
    legit = [r for r in adjudicable if r["ground_truth"] == "legitimate"]
    flagged = lambda r: r["decision"] in ("FLAG_FOR_REVIEW", "REJECTED")
    tp = sum(flagged(r) for r in fraud)
    fp = sum(flagged(r) for r in legit)
    fn, tn = len(fraud) - tp, len(legit) - fp
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / len(fraud) if fraud else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else 0.0
    count = Counter(r["decision"] for r in rows)
    latencies = [r["latency_ms"] for r in rows]
    n = len(rows)
    return {
        "n_total": n, "n_adjudicable": len(adjudicable), "n_borderline": n - len(adjudicable),
        "binary_confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision": precision, "recall": recall, "f1": f1,
        "false_positive_rate": fp / len(legit) if legit else None,
        "fraudulent_auto_approved": sum(r["decision"] == "APPROVED" for r in rows if r["ground_truth"] == "fraudulent"),
        "fraudulent_auto_approval_rate": sum(r["decision"] == "APPROVED" for r in rows if r["ground_truth"] == "fraudulent") / max(sum(r["ground_truth"] == "fraudulent" for r in rows), 1),
        "legitimate_auto_approved": sum(r["decision"] == "APPROVED" for r in legit),
        "legitimate_auto_approval_rate": sum(r["decision"] == "APPROVED" for r in legit) / len(legit) if legit else None,
        "manual_review_rate": count["FLAG_FOR_REVIEW"] / n if n else None,
        "information_request_rate": count["NEEDS_MORE_INFORMATION"] / n if n else None,
        "rejection_rate": count["REJECTED"] / n if n else None,
        "runtime_error_rate": count["VERIFICATION_ERROR"] / n if n else None,
        "decision_counts": {decision: count[decision] for decision in DECISIONS},
        "three_class_disposition_matrix": {
            label: {bucket: sum(r["ground_truth"] == label and prediction_bucket(r["decision"]) == bucket for r in rows)
                    for bucket in ("legitimate", "fraudulent", "unresolved")}
            for label in ("legitimate", "fraudulent", "borderline")},
        "latency_ms": {"mean": statistics.mean(latencies) if latencies else None,
                       "p50": statistics.median(latencies) if latencies else None,
                       "p95": sorted(latencies)[max(0, math.ceil(.95 * len(latencies)) - 1)] if latencies else None},
        "borderline_outcomes": {decision: sum(r["ground_truth"] == "borderline" and r["decision"] == decision for r in rows)
                                for decision in DECISIONS},
    }


def run_engine(cases, engine, config=None):
    results = []
    for row in cases:
        started = time.perf_counter()
        if engine == "v2":
            result = verify_v2(v2_input(row["input"]))
        else:
            result = verify_v3(v3_input(row["input"]), config or DEFAULT_CONFIG)
        elapsed = (time.perf_counter() - started) * 1000
        requirements = getattr(result, "requirements", [])
        reasons = getattr(result, "reasons", [])
        finding_codes = sorted({finding.code for finding in result.findings})
        records = {
            "case_id": row["case_id"], "ground_truth": row["ground_truth"],
            "category": row["input"]["category"], "split": row["split"],
            "scenario_family": row["scenario_family"], "document_source": row["document_source"],
            "decision": result.decision.value, "predicted_bucket": prediction_bucket(result.decision.value),
            "authenticity_score": result.authenticity_score,
            "finding_codes": finding_codes,
            "critical_missing": [r.key for r in requirements if getattr(r, "critical", True) and not r.satisfied],
            "optional_missing": [r.key for r in requirements if not getattr(r, "critical", True) and not r.satisfied],
            "information_request_count": len(result.information_requests),
            "information_requests": result.information_requests,
            "decision_explanation": " ".join(reasons),
            "runtime_error_count": len(result.errors), "errors": result.errors,
            "latency_ms": elapsed,
        }
        results.append(records)
    return results


def aggregate(rows, group_key=None):
    if not group_key:
        return binary_metrics(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[row[group_key]].append(row)
    return {key: binary_metrics(values) for key, values in sorted(groups.items())}


def run_evaluation(cases):
    paired = {}
    for name, config in (("V2_original", None), ("V3_full", DEFAULT_CONFIG)):
        paired[name] = run_engine(cases, "v2" if name.startswith("V2") else "v3", config)
    ablations = {}
    for name, config in ABLATIONS.items():
        if name == "full_v3":
            ablations[name] = paired["V3_full"]
        else:
            ablations[name] = run_engine(cases, "v3", config)
    # Exact ID and label pairing is enforced, not assumed.
    expected = [(c["case_id"], c["ground_truth"]) for c in cases]
    for name, rows in paired.items():
        if [(r["case_id"], r["ground_truth"]) for r in rows] != expected:
            raise AssertionError(f"Paired evaluation order/labels drifted for {name}")
    return paired, ablations


def write_run(cases, paired, ablations, run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    combined = {"paired": paired, "ablations": ablations}
    metrics = {}
    for name, rows in paired.items():
        metrics[name] = {"all": binary_metrics(rows),
                         "by_category": aggregate(rows, "category"),
                         "by_split": aggregate(rows, "split")}
    ablation_metrics = {name: binary_metrics(rows) for name, rows in ablations.items()}
    config = DEFAULT_CONFIG.model_dump()
    code_files = sorted((ROOT / "app/services/development_verifier_v3").glob("*.py"))
    package_hashes = {path.name: sha(path) for path in code_files}
    v2_files = sorted((ROOT / "app/services/development_verifier_v2").glob("*.py"))
    v2_hashes = {path.name: sha(path) for path in v2_files}
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata = {
        "dataset": str(DATASET.relative_to(ROOT)), "dataset_sha256": sha(DATASET),
        "dataset_rows": len(cases), "config_digest": DEFAULT_CONFIG.digest(),
        "config_sha256": sha(config_path), "v3_package_file_sha256": package_hashes,
        "v3_package_sha256": hashlib.sha256(json.dumps(package_hashes, sort_keys=True).encode()).hexdigest(),
        "v2_config_digest": DEFAULT_V2_CONFIG.digest(),
        "v2_package_sha256": hashlib.sha256(json.dumps(v2_hashes, sort_keys=True).encode()).hexdigest(),
        "python": sys.version.split()[0],
        "dependencies": {name: importlib.metadata.version(name) for name in ("pydantic", "pytest")},
        "api_requests": 0, "rag_mode": "offline full-document extraction; no semantic embedding or Gemini",
        "synthetic": True, "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps({"metrics": metrics, "ablation_metrics": ablation_metrics,
                                                           "paired": combined}, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8")
    with (run_dir / "case_level_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["engine", "case_id", "ground_truth", "category", "split", "scenario_family", "document_source",
                  "decision", "predicted_bucket", "authenticity_score", "finding_codes", "critical_missing",
                  "optional_missing", "information_request_count", "information_requests", "decision_explanation",
                  "runtime_error_count", "errors", "latency_ms"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for engine, rows in paired.items():
            for row in rows:
                writer.writerow({**row, "engine": engine,
                                 "finding_codes": ";".join(row["finding_codes"]),
                                 "critical_missing": ";".join(row["critical_missing"]),
                                 "optional_missing": ";".join(row["optional_missing"]),
                                 "information_requests": " | ".join(row["information_requests"]),
                                 "errors": ";".join(row["errors"])})
    write_report(metrics, ablation_metrics, metadata, run_dir / "report.md")
    return metrics, ablation_metrics, metadata


def pct(value):
    return "—" if value is None else f"{100 * value:.1f}%"


def write_report(metrics, ablations, metadata, path):
    lines = ["# SevaFund V3 paired development evaluation", "",
             "Synthetic development data only. No Gemini calls, embeddings, semantic RAG, or external issuer verification were used.",
             "Primary binary classification metrics exclude borderline cases; borderline outcomes are reported separately.", "",
             "## V2 versus V3", "",
             "| Engine | N | Precision | Recall | F1 | FPR (legitimate) | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Reject | Runtime errors | Mean / p50 / p95 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, data in metrics.items():
        m = data["all"]
        l = m["latency_ms"]
        lines.append(f"| {name} | {m['n_total']} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | {pct(m['false_positive_rate'])} | "
                     f"{m['fraudulent_auto_approved']} ({pct(m['fraudulent_auto_approval_rate'])}) | "
                     f"{m['legitimate_auto_approved']} ({pct(m['legitimate_auto_approval_rate'])}) | {pct(m['manual_review_rate'])} | "
                     f"{pct(m['information_request_rate'])} | {pct(m['rejection_rate'])} | {pct(m['runtime_error_rate'])} | "
                     f"{l['mean']:.2f} / {l['p50']:.2f} / {l['p95']:.2f} |")
    for name, data in metrics.items():
        m = data["all"]
        lines.extend(["", f"### {name} confusion matrices", "",
                      "Binary fraud-versus-legitimate (borderline excluded):", "",
                      "| | Predicted fraud/review | Predicted approved |", "|---|---:|---:|",
                      f"| Actual fraudulent | {m['binary_confusion_matrix']['TP']} | {m['binary_confusion_matrix']['FN']} |",
                      f"| Actual legitimate | {m['binary_confusion_matrix']['FP']} | {m['binary_confusion_matrix']['TN']} |", "",
                      "Three-class disposition matrix:", "",
                      "| Actual \\ Predicted | Approved | Flag/reject | Needs info/error |", "|---|---:|---:|---:|"])
        for actual, row in m["three_class_disposition_matrix"].items():
            lines.append(f"| {actual} | {row['legitimate']} | {row['fraudulent']} | {row['unresolved']} |")
        lines.extend(["", "Category-wise adjudicable metrics:", "",
                      "| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for category, result in data["by_category"].items():
            lines.append(f"| {category} | {result['n_total']} | {pct(result['precision'])} | {pct(result['recall'])} | {pct(result['f1'])} | "
                         f"{pct(result['false_positive_rate'])} | {pct(result['manual_review_rate'])} | {pct(result['information_request_rate'])} |")
        lines.extend(["", "Grouped validation split (families held out from development split):", "",
                      "| Split | N | Precision | Recall | F1 | FPR | Manual review | Info request |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for split, result in data["by_split"].items():
            lines.append(f"| {split} | {result['n_total']} | {pct(result['precision'])} | {pct(result['recall'])} | {pct(result['f1'])} | "
                         f"{pct(result['false_positive_rate'])} | {pct(result['manual_review_rate'])} | {pct(result['information_request_rate'])} |")
        lines.extend(["", "Borderline outcomes: " + ", ".join(f"{k}: {v}" for k, v in m["borderline_outcomes"].items()) + "."])
    lines.extend(["", "## V3 ablations", "",
                  "Each variant uses the same 180 cases. These are component contribution measurements, not independent test results.", "",
                  "| Variant | Precision | Recall | F1 | FPR | Fraud auto-approved | Manual review | Info request | Reject | Errors |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for name, m in ablations.items():
        lines.append(f"| {name} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | {pct(m['false_positive_rate'])} | "
                     f"{m['fraudulent_auto_approved']} | {pct(m['manual_review_rate'])} | {pct(m['information_request_rate'])} | "
                     f"{pct(m['rejection_rate'])} | {pct(m['runtime_error_rate'])} |")
    lines.extend(["", "## Method and limits", "",
                  "- Both versions receive the same case IDs, labels, structured campaign fields, and document text. V2 does not receive V3-only goal-currency metadata.",
                  "- Fraud precision/recall/F1/FPR use the 120 legitimate/fraudulent scenarios; borderline cases are excluded from binary metrics and shown in the 3-class disposition matrix.",
                  "- `FLAG_FOR_REVIEW` and `REJECTED` count as fraud-detection positives; `NEEDS_MORE_INFORMATION` and `VERIFICATION_ERROR` are not fraud accusations.",
                  "- A high review or information-request rate is workflow burden, not detection accuracy. Rejection requires high-confidence evidence in multiple dimensions.",
                  "- Synthetic labels and scenarios were authored in one project workflow; no independent author or human adjudication is available. Results are not estimates of real-world performance.",
                  "- Lexical/full-text deterministic checks are not semantic RAG and do not establish Gemini performance.",
                  "- Case-level explanations are in `case_level_predictions.csv`; exact inputs are in the versioned development JSONL.",
                  "- Dataset SHA-256: `" + metadata["dataset_sha256"] + "`.",
                  "- V3 package SHA-256: `" + metadata["v3_package_sha256"] + "`.",
                  "- No production code/configuration or previous benchmark was modified by this evaluator."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="development_v3")
    args = parser.parse_args()
    cases = load_cases()
    paired, ablations = run_evaluation(cases)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS / f"{args.tag}_{timestamp}"
    metrics, ablation_metrics, metadata = write_run(cases, paired, ablations, run_dir)
    print(json.dumps({"run_dir": str(run_dir), "metadata": metadata,
                      "metrics": {name: result["all"] for name, result in metrics.items()},
                      "ablations": ablation_metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
