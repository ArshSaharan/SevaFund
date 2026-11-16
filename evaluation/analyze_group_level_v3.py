"""Group-level re-analysis of saved V2/V3 predictions (no verifier is executed).

The V3 development set and the 300-case synthetic final test are built from
10-case scenario families.  This script re-expresses their saved predictions
with the label cluster as the unit (see group_uncertainty.py) and adds the
ELIGIBLE_PENDING_CONFIRMATION workflow view, keeping approval safety and
administrative workload separate.
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from group_uncertainty import case_metrics, group_report
from workflow_metrics import workflow_metrics

RUNS = Path(__file__).with_name("runs")
SOURCES = {
    "final_test_300": ("final_test_v3_31f16ae955c4/case_level_predictions.csv", "final_test_scenarios_v3.jsonl"),
    "v3_development_180": ("development_v3_frozen_20261116T100612Z/case_level_predictions.csv",
                           "development_scenarios_v3.jsonl"),
}
ENGINE_NAMES = {"V2_original": "V2", "V3_frozen": "V3", "V3_full": "V3"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(value):
    return "n/a" if value is None else f"{100 * value:.1f}%"


def ci(interval):
    return "—" if not interval else f"{100 * interval[0]:.0f}–{100 * interval[1]:.0f}%"


def load(prediction_file, dataset_file):
    cases = {}
    for line in (Path(__file__).with_name(dataset_file)).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cases[row["case_id"]] = row
    engines = {}
    for row in csv.DictReader((RUNS / prediction_file).open(encoding="utf-8")):
        engine = ENGINE_NAMES.get(row["engine"])
        if not engine:
            continue
        case = cases[row["case_id"]]
        engines.setdefault(engine, []).append({
            "case_id": row["case_id"], "ground_truth": row["ground_truth"], "category": row["category"],
            "beneficiary_type": case["input"].get("beneficiary_type"), "cluster": row["scenario_family"],
            "decision": row["decision"], "flagged": row["decision"] in ("FLAG_FOR_REVIEW", "REJECTED")})
    return engines


def render(report) -> str:
    out = ["# Group-level analysis of V2/V3 synthetic results", "",
           "Saved predictions only; no verifier was executed. Cases inside a scenario family share a template, so the "
           "label cluster (family × label) is the unit. Cluster-level rates count each cluster once (majority "
           "outcome); cluster-bootstrap intervals resample clusters. Fraud is positive; legitimate and borderline "
           "are negatives here (the V3 runner's own reports excluded borderline — FPR differs only if borderline "
           "cases are flagged, which they were not).", ""]
    for name, data in report["sources"].items():
        out += [f"## {name}", "", f"{data['cases']} cases in {data['label_clusters']} label clusters.", "",
                "| Measure | " + " | ".join(data["engines"]) + " |", "|---|" + "---:|" * len(data["engines"])]
        rows = [
            ("Homogeneous clusters (all cases same decision)", lambda e: f"{e['group']['homogeneous_clusters']}/{e['group']['label_clusters']}"),
            ("Detection ICC", lambda e: str(e["group"]["detection_icc"])),
            ("Effective sample size (detection)", lambda e: str(e["group"]["effective_sample_size_for_detection"])),
            ("Recall — case level, naive Wilson CI", lambda e: f"{pct(e['case']['recall'])} ({ci(e['group']['naive_case_level_wilson_ci95']['recall'])})"),
            ("Recall — cluster bootstrap CI", lambda e: f"{pct(e['case']['recall'])} ({ci(e['group']['cluster_bootstrap_ci95']['recall'])})"),
            ("Fraud clusters flagged", lambda e: _unit(e, "fraud_clusters_flagged")),
            ("Fraud clusters auto-approved", lambda e: _unit(e, "fraud_clusters_auto_approved")),
            ("Legitimate clusters approved", lambda e: _unit(e, "legitimate_clusters_approved")),
            ("Legitimate clusters flagged", lambda e: _unit(e, "legitimate_clusters_flagged")),
            ("Borderline clusters approved", lambda e: _unit(e, "borderline_clusters_approved")),
            ("Fraud auto-approval — cluster bootstrap CI", lambda e: f"{pct(e['case']['fraudulent_auto_approval_rate'])} ({ci(e['group']['cluster_bootstrap_ci95']['fraudulent_auto_approval_rate'])})"),
        ]
        for title, cell in rows:
            out.append(f"| {title} | " + " | ".join(cell(e) for e in data["engines"].values()) + " |")
        out += ["", "**Under the pending-confirmation workflow** (automated APPROVED → ELIGIBLE_PENDING_CONFIRMATION):", "",
                "| | " + " | ".join(data["engines"]) + " |", "|---|" + "---:|" * len(data["engines"])]
        wrows = [
            ("Safety: automatic activations", lambda w: w["approval_safety"]["automatic_activations"]),
            ("Safety: fraud detected (review/reject)", lambda w: w["approval_safety"]["fraud_detected_flag_or_reject"]),
            ("Safety: fraud held pending external confirmation", lambda w: w["approval_safety"]["fraud_pending_external_confirmation"]),
            ("Safety: borderline held pending confirmation", lambda w: w["approval_safety"]["borderline_pending_external_confirmation"]),
            ("Workload: manual reviews", lambda w: w["administrative_workload"]["manual_reviews"]),
            ("Workload: information requests", lambda w: w["administrative_workload"]["information_requests"]),
            ("Workload: external confirmations required", lambda w: w["administrative_workload"]["external_confirmations_required"]),
            ("Workload: avoidable legitimate friction (NMI/review/error)", lambda w: w["administrative_workload"]["legitimate_friction"]["information_request_or_review_avoidable"]),
        ]
        for title, cell in wrows:
            out.append(f"| {title} | " + " | ".join(str(cell(e["workflow"])) for e in data["engines"].values()) + " |")
        out += ["", "Sensitivity (assumption, not a measurement): expected fraudulent activations if external "
                "confirmation misses a share of pending fraud — V3: "
                + json.dumps(data["engines"]["V3"]["workflow"]["approval_safety"]
                             ["sensitivity_expected_fraud_activations_if_confirmation_misses"]), ""]
        out += ["Per-cluster outcomes (V3):", "", "| Cluster | Label | Size | V3 majority decision | V2 majority decision |",
                "|---|---|---:|---|---|"]
        v2_units = {(u["cluster"], u["label"]): u for u in data["engines"].get("V2", {}).get("group", {}).get("units", [])}
        for unit in data["engines"]["V3"]["group"]["units"]:
            v2 = v2_units.get((unit["cluster"], unit["label"]), {})
            out.append(f"| {unit['cluster']} | {unit['label']} | {unit['size']} | {unit['majority_decision']} | "
                       f"{v2.get('majority_decision', '—')} |")
        out.append("")
    return "\n".join(out)


def _unit(engine, key):
    u = engine["group"]["cluster_level"][key]
    return f"{u['hits']}/{u['clusters']} ({ci(u['ci95'])})"


def main(output_dir=None):
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "verifiers_executed": 0, "sources": {}}
    for name, (prediction_file, dataset_file) in SOURCES.items():
        engines = load(prediction_file, dataset_file)
        report["sources"][name] = {
            "predictions": prediction_file, "predictions_sha256": sha(RUNS / prediction_file),
            "dataset": dataset_file, "dataset_sha256": sha(Path(__file__).with_name(dataset_file)),
            "cases": len(next(iter(engines.values()))),
            "label_clusters": len({(r["cluster"], r["ground_truth"]) for r in next(iter(engines.values()))}),
            "engines": {engine: {"case": case_metrics(rows), "group": group_report(rows),
                                 "workflow": workflow_metrics(rows)} for engine, rows in sorted(engines.items())},
        }
    target = output_dir or RUNS / f"group_level_v3_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    target.mkdir(parents=True, exist_ok=False)
    (target / "results.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    (target / "report.md").write_text(render(report), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path)
    main(parser.parse_args().output_dir)
