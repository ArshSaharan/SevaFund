"""Check that the frozen benchmarks still reproduce (offline, no API call, writes nothing into evaluation/).

  1. freezes: frozen V3 (development_candidate_v3_freeze.json) and hybrid v2 (hybrid_v2_freeze.json) verify;
  2. benchmark datasets (100/150/200/300 cases) are byte-identical to the committed versions;
  3. frozen V3 re-run on the 300-case final test reproduces every recorded decision and finding code
     (runs/final_test_v3_31f16ae955c4);
  4. frozen V3 re-run on the 200/150/100-case sets reproduces every recorded decision and finding code
     (runs/diagnostic_v3_prior_benchmarks_ba1b045e8b9d);
  5. the in-sample hybrid re-scoring of the saved 10-case Gemini outputs reproduces every recorded decision
     (runs/hybrid_policy_rescoring_20261116T160320Z).
"""
import ast
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.development_verifier_v3 import verify_case  # noqa: E402
from app.services.development_verifier_v3.config import DEFAULT_CONFIG  # noqa: E402
from evaluate_development_verifier_v3 import v3_input  # noqa: E402
from freeze_hybrid_v2 import verify as verify_hybrid_v2  # noqa: E402
from verify_candidate_v3_freeze import verify as verify_v3_freeze  # noqa: E402
import rescore_hybrid_policies  # noqa: E402

RUNS = ROOT / "evaluation" / "runs"
DATASETS = {"final_test_300": "evaluation/final_test_scenarios_v3.jsonl", "fundraising_200": "evaluation/fundraising_scenarios.jsonl",
            "independent_test_150": "evaluation/independent_test_150.jsonl",
            "independent_benchmark_100": "evaluation/independent_benchmark_100.jsonl"}


def _cases(relative):
    return {c["case_id"]: c for c in (json.loads(l) for l in (ROOT / relative).read_text(encoding="utf-8").splitlines() if l.strip())}


def _replay(cases, recorded):
    mismatches = []
    for case_id, (decision, codes) in recorded.items():
        result = verify_case(v3_input(cases[case_id]["input"]), DEFAULT_CONFIG)
        now = (result.decision.value, sorted({f.code for f in result.findings}))
        if now != (decision, codes):
            mismatches.append({"case_id": case_id, "recorded": [decision, codes], "now": list(now)})
    return {"cases": len(recorded), "mismatches": mismatches, "reproduced": not mismatches}


def _codes(text):
    text = (text or "").strip()
    if not text:
        return []
    if text.startswith("["):
        return sorted(ast.literal_eval(text))
    return sorted(c.strip() for c in re.split(r"[|;,]", text) if c.strip())


def main():
    out = {"v3_freeze_valid": verify_v3_freeze()["valid"], "hybrid_v2_freeze": verify_hybrid_v2()}
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *DATASETS.values()], capture_output=True, text=True,
                           cwd=ROOT).stdout.strip()
    out["benchmark_datasets_unchanged"] = not dirty
    rows = list(csv.DictReader((RUNS / "final_test_v3_31f16ae955c4/case_level_predictions.csv").open(encoding="utf-8")))
    recorded = {r["case_id"]: (r["decision"], _codes(r["finding_codes"])) for r in rows if r["engine"] == "V3_frozen"}
    out["final_test_300_v3"] = _replay(_cases(DATASETS["final_test_300"]), recorded)
    rows = list(csv.DictReader((RUNS / "diagnostic_v3_prior_benchmarks_ba1b045e8b9d/case_level_predictions.csv").open(encoding="utf-8")))
    for name in ("fundraising_200", "independent_test_150", "independent_benchmark_100"):
        recorded = {r["case_id"]: (r["decision"], _codes(r["finding_codes"])) for r in rows
                    if r["dataset"] == name and r["engine"] == "V3"}
        out[f"{name}_v3"] = _replay(_cases(DATASETS[name]), recorded)
    saved = json.loads((RUNS / "hybrid_policy_rescoring_20261116T160320Z/results.json").read_text())
    fresh = rescore_hybrid_policies.run(saved["experiment"])
    keys = ("original_v3", "existing_hybrid", "improved_hybrid", "improved_workflow_state", "improved_triggers")
    diff = [r["case_id"] for r, s in zip(fresh["rows"], saved["rows"]) if any(r[k] != s[k] for k in keys)]
    out["hybrid_rescoring_10"] = {"cases": len(saved["rows"]), "mismatches": diff, "reproduced": not diff}
    out["all_reproduced"] = (out["v3_freeze_valid"] and out["hybrid_v2_freeze"]["valid"] and out["benchmark_datasets_unchanged"]
                             and all(v["reproduced"] for k, v in out.items() if isinstance(v, dict) and "reproduced" in v))
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    sys.exit(0 if main()["all_reproduced"] else 1)
