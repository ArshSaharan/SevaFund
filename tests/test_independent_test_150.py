import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.generate_independent_test_150 import make_cases
from evaluation.evaluate_independent_test_150 import score_rows, assert_paired

ROOT = Path(__file__).resolve().parents[1]


def test_independent_corpus_has_preregistered_counts_and_new_story_families():
    rows = make_cases()
    assert len(rows) == 150
    assert Counter(row["ground_truth"] for row in rows) == {"legitimate": 60, "fraudulent": 60, "borderline": 30}
    assert Counter(row["input"]["category"] for row in rows) == {"MEDICAL": 50, "EDUCATION": 50, "COMMUNITY": 50}
    assert len({row["case_id"] for row in rows}) == len(rows)
    assert len({row["input"]["story"] for row in rows}) == len(rows)
    assert all(row["synthetic"] and row["scenario_family"] and row["document_source"] for row in rows)
    by_family = defaultdict(list)
    for row in rows:
        by_family[row["scenario_family"]].append(row)
    assert len(by_family) == 15
    assert all(Counter(row["ground_truth"] for row in group) == {"legitimate": 4, "fraudulent": 4, "borderline": 2} for group in by_family.values())


def test_metric_mapping_separates_fraud_flags_from_followup_actions():
    rows = [
        {"case_id": "x1", "ground_truth": "fraudulent", "flagged": True, "recommendation": "FLAG_FOR_REVIEW", "retrieved_evidence_count": 1},
        {"case_id": "x2", "ground_truth": "fraudulent", "flagged": False, "recommendation": "AUTO_APPROVE", "retrieved_evidence_count": 0},
        {"case_id": "x3", "ground_truth": "legitimate", "flagged": False, "recommendation": "NEEDS_MORE_INFO", "retrieved_evidence_count": 2},
        {"case_id": "x4", "ground_truth": "borderline", "flagged": True, "recommendation": "REJECT", "retrieved_evidence_count": 1},
    ]
    metrics = score_rows(rows)
    assert metrics["confusion_matrix"] == {"true_positive": 1, "false_positive": 1, "false_negative": 1, "true_negative": 1}
    assert metrics["recall"] == 0.5
    assert metrics["false_positive_rate"] == 0.5
    assert metrics["needs_more_information_rate"] == 0.25
    assert metrics["rejection_rate"] == 0.25
    assert_paired(rows[:2], rows[:2])


def test_system_error_is_not_fraud_flag_and_is_reported_separately():
    rows = [
        {"ground_truth": "fraudulent", "flagged": False, "recommendation": "SYSTEM_ERROR"},
        {"ground_truth": "legitimate", "flagged": False, "recommendation": "AUTO_APPROVE"},
    ]
    metrics = score_rows(rows)
    assert metrics["confusion_matrix"] == {"true_positive": 0, "false_positive": 0, "false_negative": 1, "true_negative": 1}
    assert metrics["system_error_count"] == 1
    assert metrics["system_error_rate"] == 0.5


def test_generated_stories_do_not_exactly_repeat_previous_benchmarks():
    prior = set()
    for name in ("fundraising_scenarios.jsonl", "independent_benchmark_100.jsonl", "development_scenarios_v1.jsonl"):
        for line in (ROOT / "evaluation" / name).read_text().splitlines():
            old = json.loads(line)
            story = old.get("input", {}).get("story")
            if story:
                prior.add(" ".join(story.casefold().split()))
    current = {" ".join(row["input"]["story"].casefold().split()) for row in make_cases()}
    assert not (current & prior)
