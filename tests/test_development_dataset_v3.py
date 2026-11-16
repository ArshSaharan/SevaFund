import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.generate_development_dataset_v3 import generate

ROOT = Path(__file__).resolve().parents[1]


def test_v3_development_corpus_is_balanced_and_family_grouped():
    rows = generate()
    assert len(rows) == 180
    assert Counter(row["ground_truth"] for row in rows) == {
        "legitimate": 60, "fraudulent": 60, "borderline": 60}
    assert Counter(row["input"]["category"] for row in rows) == {
        "MEDICAL": 60, "EDUCATION": 60, "COMMUNITY": 60}
    groups = defaultdict(set)
    for row in rows:
        groups[row["scenario_family"]].add(row["split"])
        assert row["synthetic"] is True
        assert row["label_basis"]
        assert row["document_source"]
    assert len(groups) == 18
    assert all(len(splits) == 1 for splits in groups.values())
    assert {row["split"] for row in rows} == {"development", "validation"}


def test_materialized_v3_dataset_matches_deterministic_generator():
    path = ROOT / "evaluation" / "development_scenarios_v3.jsonl"
    materialized = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    expected = generate()
    assert [row["case_id"] for row in materialized] == [row["case_id"] for row in expected]
    assert [row["input"] for row in materialized] == [row["input"] for row in expected]
