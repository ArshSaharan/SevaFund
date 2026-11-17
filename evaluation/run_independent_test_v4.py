"""One-time independent test of the frozen systems on the sealed v4 dataset.  PREPARED, NOT EXECUTED.

Refuses to run unless ALL of the following hold:
  1. the hybrid-v2 freeze verifies (evaluation/hybrid_v2_freeze.json);
  2. the authored submission passes evaluation/validate_independent_submission.py with full protocol quotas, and its
     SHA-256 equals the sealed manifest written by the coordinator (`validate ... --seal`);
  3. an adjudicated label file (case_id,label from two blind labellers plus adjudication) covers every case and its
     SHA-256 equals the value recorded in the label seal (with Cohen's kappa) - labels are never produced by a verifier;
  4. explicit API approval (SEVAFUND_GEMINI_EVAL_APPROVED=1), a configured key and per-stage budgets;
  5. the output directory for this dataset hash does not exist yet (one run only).

Systems on identical case IDs: deterministic fallback, existing V3 + Gemini (production prompt), improved V3 +
Gemini (dated prompt + revised policy); frozen V3 is recorded inside both combined results.  `--plan` prints the
call budget without any network access.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_evaluation_framework as fw
from freeze_hybrid_v2 import verify as verify_freeze
from validate_independent_submission import validate

CONFIGS = "heuristics_lexical,gemini_rag,hybrid,gemini_rag_dated,hybrid_v2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preconditions(submission: Path, seal: Path, labels: Path, label_seal: Path) -> dict:
    problems = []
    freeze = verify_freeze()
    if not freeze["valid"]:
        problems.append(f"hybrid-v2 freeze does not verify: changed {freeze['changed']} added {freeze['added']}")
    validation = validate(submission)
    if not validation["valid"]:
        problems.append(f"submission fails the protocol ({len(validation['errors'])} errors)")
    if not seal.exists() or json.loads(seal.read_text()).get("sha256") != sha(submission):
        problems.append("submission is not sealed, or differs from its sealed manifest")
    label_rows = {}
    if labels.exists():
        label_rows = {r["case_id"]: r["label"].strip() for r in csv.DictReader(labels.open(encoding="utf-8"))}
    case_ids = [json.loads(l)["case_id"] for l in submission.read_text().splitlines() if l.strip()]
    if set(label_rows) != set(case_ids) or not all(v in {"legitimate", "fraudulent", "borderline"} for v in label_rows.values()):
        problems.append("adjudicated labels are missing, incomplete or invalid")
    if not label_seal.exists() or json.loads(label_seal.read_text()).get("sha256") != (sha(labels) if labels.exists() else None):
        problems.append("adjudicated labels are not sealed, or differ from their seal")
    return {"ok": not problems, "problems": problems, "labels": label_rows, "case_ids": case_ids}


def to_framework_cases(submission: Path, labels: dict) -> list:
    rows = []
    for line in submission.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            rows.append({"case_id": case["case_id"], "ground_truth": labels[case["case_id"]],
                         "scenario_family": case["scenario_group"], "synthetic": case["provenance"] == "synthetic",
                         "pattern": case.get("pattern"), "input": case["input"]})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--label-seal", type=Path, required=True)
    parser.add_argument("--plan", action="store_true", help="print the call budget only (no network)")
    parser.add_argument("--max-generation-calls", type=int)
    parser.add_argument("--max-embedding-calls", type=int)
    parser.add_argument("--data-authorization")
    args = parser.parse_args(argv)
    check = preconditions(args.submission, args.seal, args.labels, args.label_seal)
    if not check["ok"]:
        raise SystemExit("Refusing to run the independent test:\n- " + "\n- ".join(check["problems"]))
    digest = sha(args.submission)[:12]
    experiment = f"independent_v4_{digest}"
    directory = fw.Path(fw.__file__).with_name("runs") / experiment
    cases_path = directory.with_name(f"{experiment}_cases.jsonl")
    if not args.plan and directory.exists():
        raise SystemExit(f"{directory} exists: the independent test runs once")
    cases_path.write_text("".join(json.dumps(r) + "\n" for r in to_framework_cases(args.submission, check["labels"])))
    common = ["--dataset", str(cases_path), "--sample-per-cluster", "0", "--experiment", experiment, "--configs", CONFIGS]
    if args.data_authorization:
        common += ["--data-authorization", args.data_authorization]
    if args.plan:
        return fw.main(["plan"] + common)
    if os.environ.get(fw.APPROVAL_ENV) != "1" or not (args.max_generation_calls and args.max_embedding_calls):
        raise SystemExit("Explicit API approval and per-stage budgets are required for the independent test")
    budget = args.max_generation_calls + args.max_embedding_calls
    return fw.main(["execute"] + common + ["--max-calls", str(budget), "--max-generation-calls", str(args.max_generation_calls),
                                          "--max-embedding-calls", str(args.max_embedding_calls),
                                          "--stop-after-transient-failures", "1"])


if __name__ == "__main__":
    main()
