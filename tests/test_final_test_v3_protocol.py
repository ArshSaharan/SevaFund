from collections import Counter

from evaluation.generate_development_dataset_v3 import GROUPS
from evaluation.generate_final_test_v3 import FAMILIES


def test_final_protocol_families_are_new_and_balanced_before_generation():
    development_families = {family for labels in GROUPS.values() for specs in labels.values()
                            for family, _source in specs}
    final_families = {family for specs in FAMILIES.values() for _label, family, _source, _mode in specs}
    assert len(final_families) == 30
    assert not (development_families & final_families)
    assert all(len(specs) == 10 for specs in FAMILIES.values())
    assert Counter(label for specs in FAMILIES.values() for label, *_rest in specs) == {
        "legitimate": 10, "fraudulent": 10, "borderline": 10}
    assert Counter(label for label, *_ in FAMILIES["MEDICAL"]) == {
        "legitimate": 4, "fraudulent": 3, "borderline": 3}
    assert Counter(label for label, *_ in FAMILIES["EDUCATION"]) == {
        "legitimate": 3, "fraudulent": 4, "borderline": 3}
    assert Counter(label for label, *_ in FAMILIES["COMMUNITY"]) == {
        "legitimate": 3, "fraudulent": 3, "borderline": 4}


def test_final_protocol_includes_unverifiable_consistent_fraud_as_a_limit_case():
    hidden = [(family, mode) for specs in FAMILIES.values() for _label, family, _source, mode in specs
              if mode == "consistent_fabrication"]
    assert len(hidden) == 3
    assert all("fabricat" in family or "false" in family or "forged" in family for family, _mode in hidden)
