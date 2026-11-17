"""Interval estimates, paired tests and design calculations (standard library only)."""
import math
import random
from collections import defaultdict
from statistics import NormalDist
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

Z95 = NormalDist().inv_cdf(0.975)


def wilson(successes: float, total: float, z: float = Z95) -> Optional[Tuple[float, float]]:
    """Wilson score interval; accepts a fractional (design-effect-adjusted) sample size."""
    if not total:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


def icc_anova(groups: Sequence[Sequence[int]]) -> Optional[float]:
    """One-way ANOVA intraclass correlation for a binary outcome; None when not estimable."""
    groups = [list(g) for g in groups if g]
    n, k = sum(len(g) for g in groups), len(groups)
    if k < 2 or n <= k:
        return None
    grand = sum(sum(g) for g in groups) / n
    ss_between = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups)
    ss_within = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)
    ms_between, ms_within = ss_between / (k - 1), ss_within / (n - k)
    n0 = (n - sum(len(g) ** 2 for g in groups) / n) / (k - 1)
    denominator = ms_between + (n0 - 1) * ms_within
    if denominator <= 0:
        return None
    return (ms_between - ms_within) / denominator


def clustered_proportion(outcomes: Dict[str, List[int]]) -> dict:
    """Primary estimate: case-level proportion with a Wilson interval on the effective sample size.

    `outcomes` maps scenario group -> list of 0/1 case outcomes.  The design effect is 1 + (m - 1) * ICC with m the
    mean group size; ICC is floored at 0, and set to 1 (most conservative) when it cannot be estimated."""
    groups = [g for g in outcomes.values() if g]
    n = sum(len(g) for g in groups)
    if not n:
        return {"n": 0, "groups": 0, "successes": 0, "estimate": None, "ci": None}
    successes = sum(sum(g) for g in groups)
    m = n / len(groups)
    icc = icc_anova(groups)
    icc_used = 1.0 if icc is None else min(1.0, max(0.0, icc))
    deff = 1 + (m - 1) * icc_used
    n_eff = n / deff
    p = successes / n
    return {"n": n, "groups": len(groups), "successes": successes, "estimate": round(p, 4),
            "ci": wilson(p * n_eff, n_eff), "icc": None if icc is None else round(icc, 4),
            "icc_used": round(icc_used, 4), "design_effect": round(deff, 4), "effective_n": round(n_eff, 2)}


def cluster_bootstrap(rows: List[dict], cluster_key: str, statistic: Callable[[List[dict]], Optional[float]],
                      reps: int, seed: int, strata_key: Optional[str] = None) -> Optional[Tuple[float, float]]:
    """Percentile interval, resampling whole clusters (within strata when given)."""
    clusters = defaultdict(list)
    for row in rows:
        clusters[(row.get(strata_key) if strata_key else None, row[cluster_key])].append(row)
    by_stratum = defaultdict(list)
    for (stratum_value, _), members in clusters.items():
        by_stratum[stratum_value].append(members)
    rng = random.Random(seed)
    values = []
    for _ in range(reps):
        sample = []
        for members_list in by_stratum.values():
            for _ in range(len(members_list)):
                sample.extend(rng.choice(members_list))
        value = statistic(sample)
        if value is not None:
            values.append(value)
    if not values:
        return None
    values.sort()
    low = values[int(math.floor(0.025 * (len(values) - 1)))]
    high = values[int(math.ceil(0.975 * (len(values) - 1)))]
    return (round(low, 4), round(high, 4))


def ratio_bootstrap(clusters: Sequence[Tuple[float, float]], reps: int, seed: int) -> Optional[Tuple[float, float]]:
    """Percentile interval for sum(num)/sum(den), resampling whole clusters (scenario groups)."""
    clusters = [c for c in clusters if c[1] > 0]
    if not clusters:
        return None
    rng = random.Random(seed)
    k = len(clusters)
    values = []
    for _ in range(reps):
        num = den = 0.0
        for _ in range(k):
            a, b = clusters[rng.randrange(k)]
            num, den = num + a, den + b
        values.append(num / den)
    values.sort()
    return (round(values[int(math.floor(0.025 * (reps - 1)))], 4), round(values[int(math.ceil(0.975 * (reps - 1)))], 4))


def bootstrap_quantile(values: Sequence[float], q: float, reps: int, seed: int) -> Optional[dict]:
    values = list(values)
    if not values:
        return None
    rng = random.Random(seed)
    estimates = sorted(quantile([rng.choice(values) for _ in values], q) for _ in range(reps))
    return {"estimate": round(quantile(values, q), 3),
            "ci": (round(estimates[int(0.025 * (reps - 1))], 3), round(estimates[int(math.ceil(0.975 * (reps - 1)))], 3))}


def quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from discordant counts b (only A succeeds) and c (only B succeeds)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 6)


def holm(p_values: Dict[str, float]) -> Dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted, running = {}, 0.0
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[name] = round(running, 6)
    return adjusted


def rule_of_three_upper(n: int) -> Optional[float]:
    """Approximate one-sided 95% upper bound when zero events are observed in n independent units."""
    return round(3 / n, 4) if n else None


def mcnemar_power(n_pairs: int, discordance: float, difference: float, z_alpha: float = Z95) -> Optional[float]:
    """Approximate power of McNemar's test (Connor 1987) for a paired difference in proportions."""
    if n_pairs <= 0 or discordance <= difference * difference or difference <= 0:
        return None
    numerator = difference * math.sqrt(n_pairs) - z_alpha * math.sqrt(discordance)
    return round(NormalDist().cdf(numerator / math.sqrt(discordance - difference * difference)), 3)


def design_row(name: str, groups: Dict[str, int], cases_per_group: float, daily_limit: int, retry_share: float,
               pilot: int, assumptions: Optional[dict] = None) -> dict:
    """Precision, power and API usage for one design.  Interval half-widths are shown for the two extremes of
    clustering: ICC = 1 (one unit per group) and ICC = 0 (every case independent)."""
    a = {"recall": 0.60, "fpr": 0.05, "legit_approval": 0.70, "discordance": 0.20, "difference": 0.10,
         **(assumptions or {})}
    fraud, legit_complete, incomplete, borderline = groups["F"], groups["L"], groups["I"], groups["B"]
    legit = legit_complete + incomplete
    cases = int(round(sum(groups.values()) * cases_per_group))
    requests = cases + math.ceil(retry_share * cases) + pilot

    def half(p, n):
        interval = wilson(p * n, n)
        return round((interval[1] - interval[0]) / 2, 3) if interval else None

    return {
        "design": name, "groups": dict(groups), "total_groups": sum(groups.values()),
        "cases_per_group": cases_per_group, "cases": cases,
        "generation_requests_max": requests, "embedding_requests": 0,
        "free_tier_days_min": math.ceil(requests / daily_limit),
        "fraud_recall_halfwidth": {"icc_1": half(a["recall"], fraud), "icc_0": half(a["recall"], fraud * cases_per_group)},
        "fpr_halfwidth": {"icc_1": half(a["fpr"], legit), "icc_0": half(a["fpr"], legit * cases_per_group)},
        "legit_approval_halfwidth": {"icc_1": half(a["legit_approval"], legit_complete),
                                     "icc_0": half(a["legit_approval"], legit_complete * cases_per_group)},
        "zero_event_upper_bound_incomplete": {"icc_1": wilson(0, incomplete)[1] if incomplete else None,
                                              "icc_0": wilson(0, incomplete * cases_per_group)[1] if incomplete else None},
        "mcnemar_power_fraud_10pt": mcnemar_power(int(fraud * cases_per_group), a["discordance"], a["difference"]),
        "mcnemar_power_legit_10pt": mcnemar_power(int(legit * cases_per_group), a["discordance"], a["difference"]),
        "assumptions": a,
    }


def proportions(rows: Iterable[dict], cluster_key: str, predicate: Callable[[dict], bool]) -> Dict[str, List[int]]:
    outcomes = defaultdict(list)
    for row in rows:
        outcomes[row[cluster_key]].append(int(bool(predicate(row))))
    return dict(outcomes)
