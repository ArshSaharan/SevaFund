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


def cluster_size(groups: Sequence[Sequence[int]], rule: str = "kish") -> float:
    """Cluster size used in the design effect: Kish's size-weighted m~ = sum(m_i^2)/n (default; exact for unequal
    sizes) or the plain mean n/k."""
    n = sum(len(g) for g in groups)
    return sum(len(g) ** 2 for g in groups) / n if rule == "kish" else n / len(groups)


def clustered_proportion(outcomes: Dict[str, List[int]], size_rule: str = "kish", icc_floor: float = 0.0,
                         z: float = Z95) -> dict:
    """Primary estimate: case-level proportion with a Wilson interval on the effective sample size.

    `outcomes` maps scenario group -> list of 0/1 case outcomes.  Design effect DEFF = 1 + (m~ - 1) * ICC, with m~ the
    Kish size-weighted cluster size and ICC the one-way ANOVA estimate, floored at `icc_floor` and capped at 1; when
    ICC cannot be estimated (no within-group replication or no variation) ICC = 1, the most conservative value.
    Effective sample size n_eff = n / DEFF; the Wilson interval is computed for p-hat on n_eff."""
    groups = [g for g in outcomes.values() if g]
    n = sum(len(g) for g in groups)
    if not n:
        return {"n": 0, "groups": 0, "successes": 0, "estimate": None, "ci": None}
    successes = sum(sum(g) for g in groups)
    m = cluster_size(groups, size_rule)
    icc = icc_anova(groups)
    icc_used = 1.0 if icc is None else min(1.0, max(icc_floor, icc))
    deff = 1 + (m - 1) * icc_used
    n_eff = n / deff
    p = successes / n
    return {"n": n, "groups": len(groups), "successes": successes, "estimate": round(p, 4),
            "ci": wilson(p * n_eff, n_eff, z), "icc": None if icc is None else round(icc, 4),
            "icc_used": round(icc_used, 4), "cluster_size_kish": round(m, 4), "design_effect": round(deff, 4),
            "effective_n": round(n_eff, 2)}


def zero_event_upper(n_eff: float, alpha: float = 0.05) -> Optional[float]:
    """Exact one-sided (1 - alpha) upper bound for a rate when 0 events occur in n_eff independent units:
    1 - alpha**(1/n).  Zero observed events never establish a zero population rate."""
    return round(1 - alpha ** (1 / n_eff), 4) if n_eff and n_eff > 0 else None


def cluster_sign_flip_test(differences: Sequence[int]) -> float:
    """Exact two-sided randomisation test for paired binary data clustered by scenario group.

    `differences` holds d_k = b_k - c_k per group (discordant pairs favouring system A minus those favouring B).
    Under H0 each group's difference is symmetric about 0, so its sign is exchangeable; the null distribution of
    T = sum(d_k) is enumerated exactly by convolution.  With one case per group this is exactly the two-sided exact
    McNemar (sign) test; with larger groups it stays valid when discordance is correlated within groups."""
    values = [abs(int(d)) for d in differences if d]
    if not values:
        return 1.0
    observed = abs(sum(int(d) for d in differences))
    distribution = {0: 1.0}
    for a in values:
        nxt = defaultdict(float)
        for total, prob in distribution.items():
            nxt[total + a] += prob / 2
            nxt[total - a] += prob / 2
        distribution = nxt
    p = sum(prob for total, prob in distribution.items() if abs(total) >= observed - 1e-12)
    return round(min(1.0, p), 6)


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


def design_row(name: str, groups: Dict[str, int], cases_per_group: float, daily_limit: int, retry_share: float,
               pilot: int, assumptions: Optional[dict] = None) -> dict:
    """Precision and API usage for one design.  Interval half-widths are shown for the two extremes of clustering:
    ICC = 1 (one unit per group) and ICC = 0 (every case independent).  Paired-comparison power is simulated
    separately (ci_validation.comparison_power) because it depends on clustering and multiplicity."""
    a = {"recall": 0.60, "fpr": 0.05, "legit_approval": 0.70, **(assumptions or {})}
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
        "paired_power": "see independent_test_v5/statistical_validation.json (simulated cluster sign-flip test)",
        "assumptions": a,
    }


def proportions(rows: Iterable[dict], cluster_key: str, predicate: Callable[[dict], bool]) -> Dict[str, List[int]]:
    outcomes = defaultdict(list)
    for row in rows:
        outcomes[row[cluster_key]].append(int(bool(predicate(row))))
    return dict(outcomes)
