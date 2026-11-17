import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.evaluate_development_candidate_v2 import metrics, wilson
from evaluation.generate_development_dataset_v2 import make_cases
from evaluation.perturbations import PERTURBATIONS, perturb_case

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "development_scenarios_v2.jsonl"

# Frozen corpora and their recorded hashes: these files must never change.
FROZEN_DATASETS = {
    "fundraising_scenarios.jsonl": "cb6d08c426d8ecbfce9c661d9ef32d756ab68a052671c3fadad31d43b1cd3099",
    "independent_benchmark_100.jsonl": "fc1188c2851342683a096f4235534d9d98deb3f390bd9840feb8b13b9a07aa46",
    "independent_test_150.jsonl": "099016d5da873766fccbd199337a153de62da1ee2b6c1bb8f35b9c5b43b510e0",
    "development_scenarios_v1.jsonl": "6eb46685656dd7ceaeea6971451738a6fd2a841ca2f0d2a5e02301eb7db7eb88",
}


def rows():
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]


def test_existing_benchmarks_are_unchanged():
    for name, expected in FROZEN_DATASETS.items():
        assert hashlib.sha256((ROOT / "evaluation" / name).read_bytes()).hexdigest() == expected, name


def test_corpus_is_reproducible_from_generator():
    assert [json.loads(json.dumps(r, ensure_ascii=False)) for r in make_cases()] == rows()


def test_corpus_shape_and_family_level_split():
    data = rows()
    assert len(data) == 120 and len({r["case_id"] for r in data}) == 120
    assert Counter(r["ground_truth"] for r in data) == {"legitimate": 45, "fraudulent": 45, "borderline": 30}
    assert Counter(r["input"]["category"] for r in data) == {"MEDICAL": 40, "EDUCATION": 40, "COMMUNITY": 40}
    assert all(r["synthetic"] for r in data)
    families, sources = defaultdict(set), defaultdict(set)
    for r in data:
        families[r["scenario_family"]].add(r["split"])
        sources[r["document_source"]].add(r["split"])
    assert len(families) == 15
    assert all(len(s) == 1 for s in families.values()), "a family crosses the split"
    assert all(len(s) == 1 for s in sources.values()), "a document source crosses the split"
    split_families = Counter(next(iter(s)) for s in families.values())
    assert split_families == {"tune": 9, "validation": 6}
    for split in ("tune", "validation"):
        categories = Counter(r["input"]["category"] for r in data if r["split"] == split)
        assert len(categories) == 3, f"{split} split must cover all categories"


def test_corpus_covers_required_situations():
    data = rows()
    variants = Counter(r["variant"] for r in data)
    assert variants["no_documents"] and variants["missing_required"] and variants["consistent_fabricated"]
    assert variants["thin_evidence"] and variants["harmless_formatting"] and variants["high_cost"]
    assert any(len(r["input"]["documents"]) >= 3 for r in data)
    assert any(r["detectable_from_dossier"] is False for r in data if r["ground_truth"] == "fraudulent")


def test_corpus_does_not_repeat_prior_benchmark_stories_or_templates():
    prior = set()
    for name in FROZEN_DATASETS:
        for line in (ROOT / "evaluation" / name).read_text(encoding="utf-8").splitlines():
            story = json.loads(line).get("input", {}).get("story")
            if story:
                prior.add(" ".join(story.casefold().split()))
    stories = [" ".join(r["input"]["story"].casefold().split()) for r in rows()]
    assert not set(stories) & prior
    assert len(set(stories)) == len(stories)
    # No prior-benchmark boilerplate phrases.
    for phrase in ("[synthetic", "all fields reconcile", "preliminary review only", "the file is q"):
        assert not any(phrase in s for s in stories)


def test_perturbations_preserve_case_identity_and_change_text():
    case = next(r for r in rows() if r["variant"] == "clean" and r["input"]["category"] == "MEDICAL")
    for kind in PERTURBATIONS:
        changed = perturb_case(case, kind)
        assert changed["case_id"] == case["case_id"] and changed["ground_truth"] == case["ground_truth"]
        assert len(changed["input"]["documents"]) == len(case["input"]["documents"])
    assert perturb_case(case, "layout_collapse")["input"]["documents"][0]["content"] != case["input"]["documents"][0]["content"]


def test_perturbations_preserve_every_rupee_amount():
    """Guards the measurement itself: a perturbation that changes an amount is
    not meaning-preserving (the first currency_style version did this)."""
    from app.services.development_verifier_v2.money import find_amounts
    for case in rows():
        for kind in ("currency_style", "date_style", "name_style", "layout_collapse"):
            for before, after in zip(case["input"]["documents"], perturb_case(case, kind)["input"]["documents"]):
                original = sorted(m.value for m in find_amounts(before["content"]) if m.valid)
                perturbed = sorted(m.value for m in find_amounts(after["content"]) if m.valid)
                assert original == perturbed, (case["case_id"], kind)


def test_metrics_never_count_information_requests_as_detections():
    sample = [
        {"ground_truth": "fraudulent", "decision": "FLAG_FOR_REVIEW", "flagged": True, "latency_ms": 1},
        {"ground_truth": "fraudulent", "decision": "NEEDS_MORE_INFORMATION", "flagged": False, "latency_ms": 1},
        {"ground_truth": "fraudulent", "decision": "APPROVED", "flagged": False, "latency_ms": 1},
        {"ground_truth": "fraudulent", "decision": "VERIFICATION_ERROR", "flagged": False, "latency_ms": 1},
        {"ground_truth": "legitimate", "decision": "APPROVED", "flagged": False, "latency_ms": 1},
        {"ground_truth": "legitimate", "decision": "NEEDS_MORE_INFORMATION", "flagged": False, "latency_ms": 1},
        {"ground_truth": "borderline", "decision": "REJECTED", "flagged": True, "latency_ms": 1},
    ]
    result = metrics(sample)
    assert result["confusion_matrix"] == {"true_positive": 1, "false_positive": 1, "false_negative": 3, "true_negative": 2}
    assert result["recall"] == 0.25 and result["fraudulent_auto_approval_rate"] == 0.25
    assert result["legitimate_auto_approval_rate"] == 0.5 and result["runtime_error_rate"] == round(1 / 7, 4)
    assert result["secondary_convention_nmi_counts_as_detection"]["recall"] == 0.5
    lo, hi = wilson(1, 4)
    assert 0 < lo < 0.25 < hi < 1
