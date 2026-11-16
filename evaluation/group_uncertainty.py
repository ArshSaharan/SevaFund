"""Group-aware metrics and uncertainty for template-generated benchmarks.

Synthetic benchmarks are built from scenario groups whose cases share a
template, so cases inside a group are not independent.  This module treats the
*label cluster* - (scenario group, ground-truth label) - as the unit:

* cluster-level rates: each cluster contributes one vote (its majority outcome),
  with Wilson 95% intervals over clusters;
* cluster-bootstrap 95% intervals for the usual case-level metrics
  (clusters are resampled with replacement within each label);
* homogeneity, intraclass correlation (ANOVA estimator) and the Kish effective
  sample size n / (1 + (m - 1) * ICC) for the detection outcome.

Rows need: ground_truth, decision, flagged (bool), cluster (hashable).
Fraud is the positive class; a detection is `flagged`.  Pending confirmation
and information requests are never detections.
"""
import math
import random
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional

DEFAULT_SEED = 20261116


def wilson(successes: int, total: int, z: float = 1.96) -> Optional[List[float]]:
    if not total:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def _ratio(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def case_metrics(rows: List[dict], include_borderline_as_negative: bool = True) -> dict:
    fraud = [r for r in rows if r["ground_truth"] == "fraudulent"]
    legit = [r for r in rows if r["ground_truth"] == "legitimate"]
    negatives = [r for r in rows if r["ground_truth"] != "fraudulent"] if include_borderline_as_negative else legit
    tp = sum(r["flagged"] for r in fraud)
    fp = sum(r["flagged"] for r in negatives)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / len(fraud) if fraud else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
    n = len(rows)
    count = Counter(r["decision"] for r in rows)
    return {
        "cases": n,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "false_negative": len(fraud) - tp,
                             "true_negative": len(negatives) - fp},
        "precision": None if precision is None else round(precision, 4),
        "recall": None if recall is None else round(recall, 4), "f1": round(f1, 4),
        "false_positive_rate": _ratio(fp, len(negatives)),
        "legitimate_false_positive_rate": _ratio(sum(r["flagged"] for r in legit), len(legit)),
        "fraudulent_auto_approval_rate": _ratio(sum(r["decision"] == "APPROVED" for r in fraud), len(fraud)),
        "legitimate_auto_approval_rate": _ratio(sum(r["decision"] == "APPROVED" for r in legit), len(legit)),
        "manual_review_rate": _ratio(count["FLAG_FOR_REVIEW"], n),
        "information_request_rate": _ratio(count["NEEDS_MORE_INFORMATION"], n),
        "rejection_rate": _ratio(count["REJECTED"], n),
        "runtime_error_rate": _ratio(count["VERIFICATION_ERROR"], n),
        "decision_counts": dict(count),
        "decision_matrix": {label: dict(Counter(r["decision"] for r in rows if r["ground_truth"] == label))
                            for label in ("legitimate", "fraudulent", "borderline")},
    }


def clusters(rows: List[dict]) -> Dict[tuple, List[dict]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["cluster"], row["ground_truth"])].append(row)
    return grouped


def _majority(values):
    return Counter(values).most_common(1)[0][0]


def icc_binary(groups: List[List[int]]) -> Optional[float]:
    """One-way ANOVA ICC estimator for a 0/1 outcome (unequal group sizes)."""
    groups = [g for g in groups if g]
    k, n = len(groups), sum(len(g) for g in groups)
    if k < 2 or n <= k:
        return None
    grand = sum(sum(g) for g in groups) / n
    msb = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups) / (k - 1)
    msw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups) / (n - k)
    n0 = (n - sum(len(g) ** 2 for g in groups) / n) / (k - 1)
    if msb + (n0 - 1) * msw == 0:
        return 1.0 if msw == 0 else 0.0     # no variation anywhere: outcomes are fully determined by group
    return round((msb - msw) / (msb + (n0 - 1) * msw), 4)


def cluster_bootstrap(rows: List[dict], metric: Callable[[List[dict]], Optional[float]], reps: int = 5000,
                      seed: int = DEFAULT_SEED) -> Optional[List[float]]:
    """Percentile interval from resampling label clusters (stratified by label)."""
    by_label = defaultdict(list)
    for (cluster, label), members in clusters(rows).items():
        by_label[label].append(members)
    rng = random.Random(seed)
    values = []
    for _ in range(reps):
        sample = []
        for members_list in by_label.values():
            for _ in range(len(members_list)):
                sample.extend(rng.choice(members_list))
        value = metric(sample)
        if value is not None:
            values.append(value)
    if not values:
        return None
    values.sort()
    return [round(values[int(0.025 * (len(values) - 1))], 4), round(values[int(0.975 * (len(values) - 1))], 4)]


def group_report(rows: List[dict], reps: int = 5000) -> dict:
    """Cluster-level view plus cluster-robust intervals for the main case-level rates."""
    grouped = clusters(rows)
    units = []
    for (cluster, label), members in sorted(grouped.items(), key=lambda item: str(item[0])):
        decisions = [m["decision"] for m in members]
        units.append({"cluster": cluster, "label": label, "size": len(members),
                      "majority_decision": _majority(decisions), "homogeneous": len(set(decisions)) == 1,
                      "flag_share": round(sum(m["flagged"] for m in members) / len(members), 4),
                      "approval_share": round(sum(m["decision"] == "APPROVED" for m in members) / len(members), 4)})
    def unit_rate(label, predicate):
        chosen = [u for u in units if u["label"] == label]
        hits = sum(predicate(u) for u in chosen)
        return {"clusters": len(chosen), "hits": hits, "rate": _ratio(hits, len(chosen)),
                "ci95": wilson(hits, len(chosen))}
    flagged_vote = lambda u: u["flag_share"] > 0.5
    approved_vote = lambda u: u["approval_share"] > 0.5
    rate = lambda label, key: (lambda sample: (lambda chosen: sum(r[key] for r in chosen) / len(chosen) if chosen
                                               else None)([r for r in sample if r["ground_truth"] == label]))
    detection = [[int(m["flagged"]) for m in members] for members in grouped.values()]
    icc = icc_binary(detection)
    n = len(rows)
    mean_size = n / len(grouped) if grouped else 0
    effective = None if icc is None else round(n / (1 + (mean_size - 1) * max(icc, 0.0)), 1)
    for row in rows:
        row.setdefault("_approved", row["decision"] == "APPROVED")
    return {
        "cases": n, "label_clusters": len(grouped), "mean_cluster_size": round(mean_size, 2),
        "homogeneous_clusters": sum(u["homogeneous"] for u in units),
        "detection_icc": icc, "effective_sample_size_for_detection": effective,
        "cluster_level": {
            "fraud_clusters_flagged": unit_rate("fraudulent", flagged_vote),
            "fraud_clusters_auto_approved": unit_rate("fraudulent", approved_vote),
            "legitimate_clusters_flagged": unit_rate("legitimate", flagged_vote),
            "legitimate_clusters_approved": unit_rate("legitimate", approved_vote),
            "borderline_clusters_approved": unit_rate("borderline", approved_vote),
        },
        "cluster_bootstrap_ci95": {
            "recall": cluster_bootstrap(rows, rate("fraudulent", "flagged"), reps),
            "legitimate_false_positive_rate": cluster_bootstrap(rows, rate("legitimate", "flagged"), reps),
            "fraudulent_auto_approval_rate": cluster_bootstrap(rows, rate("fraudulent", "_approved"), reps),
            "legitimate_auto_approval_rate": cluster_bootstrap(rows, rate("legitimate", "_approved"), reps),
        },
        "naive_case_level_wilson_ci95": {
            "recall": wilson(sum(r["flagged"] for r in rows if r["ground_truth"] == "fraudulent"),
                             sum(r["ground_truth"] == "fraudulent" for r in rows)),
        },
        "units": units,
    }
