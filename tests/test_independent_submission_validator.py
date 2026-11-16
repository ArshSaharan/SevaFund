import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

from validate_independent_submission import kappa, validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "evaluation/independent_test_v4/example_case.json").read_text())


def write(tmp_path, cases, name="submission.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    return path


def variant(**changes):
    case = copy.deepcopy(EXAMPLE)
    for key, value in changes.items():
        case[key] = value
    return case


def errors(tmp_path, cases):
    return validate(write(tmp_path, cases), quotas={})["errors"]


def test_example_case_is_structurally_valid(tmp_path):
    result = validate(write(tmp_path, [EXAMPLE]), quotas={})
    assert result["valid"], result["errors"]


def test_more_than_three_cases_per_group_is_rejected(tmp_path):
    cases = [variant(case_id=f"T4-MED-0001-{c}", input={**EXAMPLE["input"], "story": f"{c} " * 5 + EXAMPLE["input"]["story"]})
             for c in "ABCD"]
    assert any("maximum 3" in e for e in errors(tmp_path, cases))


def test_gold_evidence_must_name_a_document(tmp_path):
    assert any("gold_evidence_titles must name" in e for e in errors(tmp_path, [variant(gold_evidence_titles=["Nope"])]))


def test_consistent_fabrication_must_be_revealable_by_an_independent_party(tmp_path):
    env = {c: {"independent_response": "CONFIRMED"} for c in ("BENEFICIARY", "PAYMENT_DESTINATION", "INSTITUTION")}
    assert any("revealed" in e for e in errors(tmp_path, [variant(external_environment=env)]))


def test_missing_external_environment_entry_is_rejected(tmp_path):
    env = copy.deepcopy(EXAMPLE["external_environment"])
    del env["PAYMENT_DESTINATION"]
    assert any("PAYMENT_DESTINATION" in e for e in errors(tmp_path, [variant(external_environment=env)]))


def test_keyword_free_cases_cannot_use_known_scam_wording(tmp_path):
    data = {**EXAMPLE["input"], "story": "Please transfer straight to my cousin's GPay number, the hospital is slow."}
    assert any("keyword_free" in e for e in errors(tmp_path, [variant(pattern="keyword_free", input=data)]))


def test_story_copied_from_a_previous_corpus_is_rejected(tmp_path):
    prior = json.loads((ROOT / "evaluation/independent_test_150.jsonl").read_text().splitlines()[0])
    data = {**EXAMPLE["input"], "story": prior["input"]["story"]}
    assert any("near-duplicate" in e for e in errors(tmp_path, [variant(input=data)]))


def test_provenance_must_match_synthetic_flag(tmp_path):
    assert any("provenance" in e for e in errors(tmp_path, [variant(synthetic=False)]))


def test_protocol_quotas_are_enforced(tmp_path):
    result = validate(write(tmp_path, [EXAMPLE]))
    assert not result["valid"]
    assert any("MEDICAL: 0 legitimate groups" in e for e in result["errors"])


def test_cohens_kappa(tmp_path):
    header = "case_id,labeller_id,label,expected_workflow_end_state,detectable_from_dossier," \
             "detectable_by_external_confirmation,gold_evidence_titles,notes\n"
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text(header + "1,L1,fraudulent,,,,,\n2,L1,legitimate,,,,,\n3,L1,borderline,,,,,\n4,L1,legitimate,,,,,\n")
    b.write_text(header + "1,L2,fraudulent,,,,,\n2,L2,legitimate,,,,,\n3,L2,legitimate,,,,,\n4,L2,legitimate,,,,,\n")
    result = kappa(a, b)
    assert result["cases"] == 4 and result["disagreements"] == ["3"]
    assert 0.5 < result["kappa"] < 0.7
