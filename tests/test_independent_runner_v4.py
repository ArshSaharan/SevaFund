"""The independent-test runner refuses to run unless the freeze, dataset seal and label seal all hold.
No network access: every refusal happens before any API call."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_independent_test_v4 as runner  # noqa: E402
from freeze_hybrid_v2 import verify  # noqa: E402

EXAMPLE = json.loads((ROOT / "evaluation/independent_test_v4/example_case.json").read_text())


def setup(tmp_path, seal_ok=True, labels_ok=True, label_seal_ok=True):
    submission = tmp_path / "submission.jsonl"
    submission.write_text(json.dumps(EXAMPLE) + "\n")
    seal = tmp_path / "seal.json"
    seal.write_text(json.dumps({"sha256": runner.sha(submission) if seal_ok else "0" * 64}))
    labels = tmp_path / "labels.csv"
    with labels.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "label"])
        if labels_ok:
            writer.writerow([EXAMPLE["case_id"], "fraudulent"])
    label_seal = tmp_path / "label_seal.json"
    label_seal.write_text(json.dumps({"sha256": runner.sha(labels) if label_seal_ok else "x", "kappa": 0.8}))
    return submission, seal, labels, label_seal


def test_hybrid_v2_freeze_verifies():
    result = verify()
    assert result["valid"], result


def test_runner_refuses_a_submission_that_fails_the_protocol(tmp_path):
    submission, seal, labels, label_seal = setup(tmp_path)
    with pytest.raises(SystemExit, match="fails the protocol"):
        runner.main([str(submission), "--seal", str(seal), "--labels", str(labels), "--label-seal", str(label_seal), "--plan"])


@pytest.mark.parametrize("kwargs,message", [
    ({"seal_ok": False}, "not sealed"), ({"labels_ok": False}, "labels are missing"),
    ({"label_seal_ok": False}, "labels are not sealed")])
def test_runner_refuses_unsealed_or_unlabelled_data(tmp_path, kwargs, message):
    check = runner.preconditions(*setup(tmp_path, **kwargs))
    assert not check["ok"] and any(message in p for p in check["problems"])


def test_runner_refuses_when_the_freeze_is_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "verify_freeze", lambda: {"valid": False, "changed": ["x.py"], "added": []})
    check = runner.preconditions(*setup(tmp_path))
    assert any("freeze does not verify" in p for p in check["problems"])


def test_framework_cases_take_labels_from_adjudication_not_authors(tmp_path):
    submission, *_ = setup(tmp_path)
    rows = runner.to_framework_cases(submission, {EXAMPLE["case_id"]: "borderline"})
    assert rows[0]["ground_truth"] == "borderline" and rows[0]["scenario_family"] == EXAMPLE["scenario_group"]


def test_execution_requires_explicit_api_approval(tmp_path, monkeypatch):
    submission, seal, labels, label_seal = setup(tmp_path)
    monkeypatch.setattr(runner, "preconditions", lambda *a: {"ok": True, "problems": [], "labels": {EXAMPLE["case_id"]: "fraudulent"},
                                                              "case_ids": [EXAMPLE["case_id"]]})
    monkeypatch.setattr(runner.fw, "Path", lambda *_: tmp_path / "x.py")
    monkeypatch.delenv(runner.fw.APPROVAL_ENV, raising=False)
    with pytest.raises(SystemExit, match="Explicit API approval"):
        runner.main([str(submission), "--seal", str(seal), "--labels", str(labels), "--label-seal", str(label_seal),
                     "--max-generation-calls", "5", "--max-embedding-calls", "5"])
