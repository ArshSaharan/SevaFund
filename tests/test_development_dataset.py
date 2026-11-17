import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "development_scenarios_v1.jsonl"


def test_development_dataset_has_balanced_grouped_synthetic_cases():
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line]
    assert len(rows) == 120
    assert Counter(row["ground_truth"] for row in rows) == {
        "legitimate": 48, "fraudulent": 48, "borderline": 24,
    }
    assert len({row["case_id"] for row in rows}) == 120
    assert len({row["input"]["story"] for row in rows}) == 120
    assert all(row["synthetic"] for row in rows)
    assert all(row.get("scenario_family") and row.get("document_source") for row in rows)
    assert all(row.get("evidence_relation") in {"supports", "contradicts", "incomplete", "unavailable"} for row in rows)
    families = defaultdict(list)
    sources = defaultdict(set)
    folds = defaultdict(set)
    for row in rows:
        families[row["scenario_family"]].append(row)
        sources[row["scenario_family"]].add(row["document_source"])
        folds[row["scenario_family"]].add(row["group_fold"])
    assert len(families) == 12
    for family, cases in families.items():
        assert len(cases) == 10, family
        assert Counter(row["ground_truth"] for row in cases) == {
            "legitimate": 4, "fraudulent": 4, "borderline": 2,
        }
        assert len(sources[family]) == 1
        assert len(folds[family]) == 1


def test_development_dataset_is_novel_against_prior_corpora():
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line]
    prior_files = [ROOT / "evaluation" / "fundraising_scenarios.jsonl", ROOT / "evaluation" / "independent_benchmark_100.jsonl"]
    prior_stories = set()
    for path in prior_files:
        for line in path.read_text().splitlines():
            case = json.loads(line)
            story = case.get("input", {}).get("story")
            if story:
                prior_stories.add(story.casefold())
    assert not ({row["input"]["story"].casefold() for row in rows} & prior_stories)
