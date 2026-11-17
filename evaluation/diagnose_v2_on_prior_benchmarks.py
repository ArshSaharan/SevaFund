"""One-shot diagnostic of the FROZEN v2 candidate on the three earlier synthetic corpora.

These corpora are not untouched test sets: the 150-case set was already analysed
and motivated this development cycle; two of its cases (crash regressions) and
two cases of the 100-case set appear in unit tests.  Results are therefore
diagnostic, out-of-distribution evidence only - never a final performance claim -
and the candidate must not be changed in response to them.

Datasets are read, never written.  Gemini is disabled.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.services.development_verifier_v2 import CaseInput, DocumentInput, verify_case
from evaluate_development_candidate_v2 import FREEZE_MANIFEST, grouped, metrics, package_digest

CORPORA = {
    "independent_test_150": ("independent_test_150.jsonl", "independent_test_150_20261115T170654Z"),
    "independent_benchmark_100": ("independent_benchmark_100.jsonl", "independent_benchmark_100_offline_20261115T153504Z"),
    "fundraising_200": ("fundraising_scenarios.jsonl", None),
}
LEGACY = {"AUTO_APPROVE": "APPROVED", "NEEDS_MORE_INFO": "NEEDS_MORE_INFORMATION", "FLAG_FOR_REVIEW": "FLAG_FOR_REVIEW",
          "REJECT": "REJECTED", "SYSTEM_ERROR": "VERIFICATION_ERROR"}


def prior_metrics(run_name):
    """Previously recorded baseline / v1 results, re-expressed in this report's metric set."""
    if not run_name:
        return None
    path = Path(__file__).with_name("runs") / run_name
    found = {}
    for engine, filename in (("baseline", "baseline.json"), ("candidate_v1", "candidate.json")):
        if (path / filename).exists():
            rows = json.loads((path / filename).read_text())["predictions"]
            found[engine] = metrics([{**r, "decision": LEGACY.get(r["recommendation"], r["recommendation"]),
                                      "flagged": bool(r["flagged"])} for r in rows])
    return found or None


def run(output_dir=None):
    manifest = json.loads(FREEZE_MANIFEST.read_text())
    if manifest["v2_package"]["combined"] != package_digest()["combined"]:
        raise SystemExit("v2 differs from the freeze manifest; the diagnostic is only meaningful for the frozen candidate")
    settings.GEMINI_API_KEY = ""
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "v2_package": package_digest()["combined"],
              "interpretation": __doc__.strip(), "corpora": {}}
    for name, (filename, prior_run) in CORPORA.items():
        path = Path(__file__).with_name(filename)
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = []
        for case in cases:
            data = case["input"]
            documents = [DocumentInput(title=d.get("title", "Document"), doc_type=d.get("doc_type", "OTHER"),
                                       text=d.get("content", "")) for d in data.get("documents", [])]
            result = verify_case(CaseInput(title=data["title"], category=data["category"], story=data["story"],
                                           goal_amount=data["goal_amount"], beneficiary_name=data.get("beneficiary_name"),
                                           beneficiary_type=data.get("beneficiary_type"), documents=documents))
            rows.append({"case_id": case["case_id"], "ground_truth": case["ground_truth"],
                         "category": data["category"], "decision": result.decision.value,
                         "flagged": result.decision.value in {"FLAG_FOR_REVIEW", "REJECTED"},
                         "finding_codes": sorted({f.code for f in result.findings}),
                         "unmet": [r.key for r in result.requirements if not r.satisfied]})
        false_positive_codes = Counter(code for r in rows if r["flagged"] and r["ground_truth"] != "fraudulent"
                                       for code in r["finding_codes"])
        missed = Counter(r["decision"] for r in rows if r["ground_truth"] == "fraudulent" and not r["flagged"])
        report["corpora"][name] = {
            "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "cases": len(rows),
            "labels": dict(Counter(r["ground_truth"] for r in rows)),
            "candidate_v2": metrics(rows), "candidate_v2_by_category": grouped(rows, "category"),
            "previously_recorded": prior_metrics(prior_run),
            "finding_codes_behind_false_positives": dict(false_positive_codes.most_common()),
            "decisions_for_missed_fraud": dict(missed),
            "predictions": rows,
        }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output_dir or Path(__file__).with_name("runs") / f"diagnostic_v2_prior_benchmarks_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    (target / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {name: {k: c["candidate_v2"][k] for k in ("precision", "recall", "f1", "false_positive_rate",
                                                         "fraudulent_auto_approval_rate", "legitimate_auto_approval_rate",
                                                         "needs_more_information_rate", "runtime_error_rate")}
               for name, c in report["corpora"].items()}
    print(json.dumps({"results": str(target / "results.json"), "summary": summary}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path)
    run(parser.parse_args().output_dir)
