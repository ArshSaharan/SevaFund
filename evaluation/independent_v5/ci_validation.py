"""Offline Monte Carlo validation of the v5 statistical methods (standard library only; no data, no API).

  1. Coverage of 95% intervals for a proportion when cases are clustered in scenario groups (beta-binomial groups of
     1-3 cases, ICC 0-0.9): naive Wilson, design-effect Wilson (mean or Kish cluster size, optional ICC floor),
     group-count Wilson, cluster bootstrap.
  2. Type I error of paired tests when discordance is correlated within groups: exact McNemar (ignores groups)
     versus the cluster sign-flip test.
  3. Coverage of the cluster-bootstrap interval for a paired difference.
  4. Power of the paired comparison against hybrid v2 under stated assumptions (unadjusted and Holm worst case).
  5. Operating characteristics of recall thresholds: P(lower bound >= T | true recall, effective n).
  6. One-sided upper bounds after zero observed events.
"""
import json
import math
import random
from collections import defaultdict
from typing import Dict, List

from . import stats

DESIGNS = {
    "A_groups90_size1to3": {"groups": 90, "sizes": (1, 2, 3), "weights": (0.25, 0.5, 0.25)},
    "A_groups45_size1to3": {"groups": 45, "sizes": (1, 2, 3), "weights": (0.25, 0.5, 0.25)},
    "B_groups90_size1": {"groups": 90, "sizes": (1,), "weights": (1.0,)},
    "B_groups45_size1": {"groups": 45, "sizes": (1,), "weights": (1.0,)},
    "D_groups30_size1": {"groups": 30, "sizes": (1,), "weights": (1.0,)},
}
POWER_DESIGNS = (("A: 90 groups per stratum, 1-3 cases", "A_groups90_size1to3"),
                 ("B: 90 groups per stratum, 1 case", "B_groups90_size1"),
                 ("C: 45 groups per stratum, 1 case", "B_groups45_size1"),
                 ("D: 30 groups per stratum, 1 case", "D_groups30_size1"))


def _sizes(rng: random.Random, design: dict) -> List[int]:
    return rng.choices(design["sizes"], design["weights"], k=design["groups"])


def _clustered_binary(rng: random.Random, sizes: List[int], p: float, rho: float) -> Dict[int, List[int]]:
    """Beta-binomial groups: group probability ~ Beta with mean p and intraclass correlation rho."""
    out = {}
    for g, size in enumerate(sizes):
        if rho <= 0:
            pg = p
        else:
            a, b = p * (1 - rho) / rho, (1 - p) * (1 - rho) / rho
            pg = rng.betavariate(a, b)
        out[g] = [int(rng.random() < pg) for _ in range(size)]
    return out


def _methods(outcomes: Dict[int, List[int]]) -> Dict[str, tuple]:
    n = sum(len(v) for v in outcomes.values())
    x = sum(sum(v) for v in outcomes.values())
    k = len(outcomes)
    return {
        "naive_wilson": stats.wilson(x, n),
        "deff_mean_size": stats.clustered_proportion({str(g): v for g, v in outcomes.items()}, "mean")["ci"],
        "deff_kish": stats.clustered_proportion({str(g): v for g, v in outcomes.items()}, "kish")["ci"],
        "deff_kish_floor_0.1": stats.clustered_proportion({str(g): v for g, v in outcomes.items()}, "kish", 0.1)["ci"],
        "group_count_wilson": stats.wilson(x / n * k, k),
    }


def proportion_coverage(sims: int = 2000, seed: int = 20261118) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    for design_name, design in DESIGNS.items():
        if design_name.startswith("D"):
            continue
        rhos = (0.0, 0.3, 0.6, 0.9) if design["sizes"] != (1,) else (0.0,)
        for p in (0.05, 0.15, 0.5, 0.75, 0.85, 0.95):
            for rho in rhos:
                hits, widths = defaultdict(int), defaultdict(float)
                for _ in range(sims):
                    outcomes = _clustered_binary(rng, _sizes(rng, design), p, rho)
                    for method, ci in _methods(outcomes).items():
                        hits[method] += ci[0] <= p <= ci[1]
                        widths[method] += ci[1] - ci[0]
                for method in hits:
                    rows.append({"design": design_name, "p": p, "icc": rho, "method": method,
                                 "coverage": round(hits[method] / sims, 4), "mean_width": round(widths[method] / sims, 4)})
    return rows


def bootstrap_coverage(sims: int = 400, reps: int = 400, seed: int = 20261119) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    design = DESIGNS["A_groups90_size1to3"]
    for p in (0.05, 0.5, 0.85):
        for rho in (0.0, 0.6):
            hits = 0
            for i in range(sims):
                outcomes = _clustered_binary(rng, _sizes(rng, design), p, rho)
                ci = stats.ratio_bootstrap([(sum(v), len(v)) for v in outcomes.values()], reps, seed + i)
                hits += ci[0] <= p <= ci[1]
            rows.append({"design": "A_groups90_size1to3", "p": p, "icc": rho, "method": "cluster_bootstrap_percentile",
                         "coverage": round(hits / sims, 4)})
    return rows


def _paired_groups(rng, sizes, q, pi, kappa):
    """Per group: discordant cases occur with probability q; the group has a direction s = +1 with probability pi;
    each discordant case takes direction s with probability kappa (kappa = 0.5: independent directions)."""
    groups = []
    for size in sizes:
        s = 1 if rng.random() < pi else -1
        d = 0
        for _ in range(size):
            if rng.random() < q:
                d += s if rng.random() < kappa else -s
        groups.append((d, size))
    return groups


def paired_type1(sims: int = 3000, seed: int = 20261120, alpha: float = 0.05) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    for design_name in ("A_groups90_size1to3", "B_groups90_size1"):
        design = DESIGNS[design_name]
        for q in (0.1, 0.3):
            for kappa in (0.5, 0.8, 1.0):
                if design["sizes"] == (1,) and kappa != 0.5:
                    continue
                naive = flip = 0
                for _ in range(sims):
                    groups = _paired_groups(rng, _sizes(rng, design), q, 0.5, kappa)
                    b = sum(max(d, 0) for d, _ in groups)
                    c = sum(max(-d, 0) for d, _ in groups)
                    naive += stats.mcnemar_exact(b, c) < alpha
                    flip += stats.cluster_sign_flip_test([d for d, _ in groups]) < alpha
                rows.append({"design": design_name, "discordance": q, "within_group_direction_agreement": kappa,
                             "type1_exact_mcnemar_ignoring_groups": round(naive / sims, 4),
                             "type1_cluster_sign_flip": round(flip / sims, 4)})
    return rows


def paired_difference_coverage(sims: int = 400, reps: int = 400, seed: int = 20261121) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    design = DESIGNS["A_groups90_size1to3"]
    for q, pi, kappa in ((0.2, 0.75, 0.8), (0.15, 1.0, 1.0), (0.3, 0.5, 0.8)):
        true = q * (2 * pi - 1) * (2 * kappa - 1)
        hits = 0
        for i in range(sims):
            groups = _paired_groups(rng, _sizes(rng, design), q, pi, kappa)
            ci = stats.ratio_bootstrap([(float(d), size) for d, size in groups], reps, seed + i)
            hits += ci[0] <= true <= ci[1]
        rows.append({"discordance": q, "true_difference": round(true, 4), "coverage": round(hits / sims, 4)})
    return rows


def comparison_power(sims: int = 1500, seed: int = 20261122) -> List[dict]:
    """Power of the cluster sign-flip test for a paired difference d with discordance q.  Effects are mostly
    one-directional (q = d + 0.02, as when one system is uniformly stricter) or mixed (q = d + 0.10).  Design A
    assumes every discordant pair in a group points the same way (kappa = 1, maximal clustering); Holm's worst case for four comparisons is alpha/4."""
    rng = random.Random(seed)
    rows = []
    kappa = 1.0
    for label_design, design_name in POWER_DESIGNS:
        design = DESIGNS[design_name]
        for d in (0.05, 0.10, 0.15, 0.25):
            for label, q in (("one_directional", d + 0.02), ("mixed", d + 0.10)):
                pi = (1 + d / (q * (2 * kappa - 1))) / 2
                if not 0 <= pi <= 1:
                    continue
                unadjusted = holm_worst = 0
                for _ in range(sims):
                    groups = _paired_groups(rng, _sizes(rng, design), q, pi, kappa)
                    p = stats.cluster_sign_flip_test([g[0] for g in groups])
                    unadjusted += p < 0.05
                    holm_worst += p < 0.0125
                rows.append({"design": label_design, "difference": d, "pattern": label, "discordance": round(q, 3),
                             "power_alpha_0.05": round(unadjusted / sims, 3),
                             "power_holm_worst_case_alpha_0.0125": round(holm_worst / sims, 3)})
    return rows


def recall_operating_characteristics() -> dict:
    """Exact binomial: probability that the Wilson lower bound clears T, for integer effective sizes."""
    out = {"minimum_observed_recall": {}, "probability_criterion_met": []}
    for n in (15, 22, 36, 45, 68, 80, 90):
        for t in (0.50, 0.70, 0.80, 0.85):
            needed = next((x for x in range(n + 1) if stats.wilson(x, n)[0] >= t), None)
            out["minimum_observed_recall"][f"n_eff={n}|T={t}"] = None if needed is None else round(needed / n, 3)
        for true in (0.70, 0.75, 0.80, 0.85, 0.90, 0.95):
            row = {"n_eff": n, "true_recall": true}
            for t in (0.50, 0.70, 0.80, 0.85):
                needed = next((x for x in range(n + 1) if stats.wilson(x, n)[0] >= t), n + 1)
                row[f"P(met|T={t})"] = round(sum(math.comb(n, x) * true ** x * (1 - true) ** (n - x)
                                                 for x in range(needed, n + 1)), 3)
            out["probability_criterion_met"].append(row)
    return out


def _p_met(n: int, true: float, threshold: float, bound: str) -> float:
    """Exact binomial probability that a Wilson bound on n effective units clears the threshold."""
    ok = [x for x in range(n + 1) if (stats.wilson(x, n)[0] >= threshold if bound == "lower"
                                      else stats.wilson(x, n)[1] <= threshold)]
    return sum(math.comb(n, x) * true ** x * (1 - true) ** (n - x) for x in ok)


def verdict_operating_characteristics() -> List[dict]:
    """Probability of meeting the primary endpoint (H1) and the two key secondary criteria (K1, K2), and the
    approximate joint probability of the overall minimum-standard verdict (treating the three as independent and
    the gates as passed).  Effective sizes bracket the clustering range for each design."""
    scenarios = {"A (ICC 1 .. 0.1)": {"H1": (45, 80), "K1": (135, 240), "K2": (90, 160)},
                 "B": {"H1": (45, 45), "K1": (135, 135), "K2": (90, 90)},
                 "C": {"H1": (22, 22), "K1": (75, 75), "K2": (45, 45)},
                 "D": {"H1": (15, 15), "K1": (45, 45), "K2": (30, 30)}}
    truths = [{"recall": 0.85, "fpr": 0.05, "approval": 0.65}, {"recall": 0.90, "fpr": 0.03, "approval": 0.75}]
    rows = []
    for design, sizes in scenarios.items():
        for truth in truths:
            for which, index in (("conservative", 0), ("optimistic", 1)):
                h1 = _p_met(sizes["H1"][index], truth["recall"], 0.70, "lower")
                k1 = _p_met(sizes["K1"][index], truth["fpr"], 0.10, "upper")
                k2 = _p_met(sizes["K2"][index], truth["approval"], 0.50, "lower")
                rows.append({"design": design, "clustering": which, **{f"true_{k}": v for k, v in truth.items()},
                             "n_eff": {k: v[index] for k, v in sizes.items()}, "P_H1": round(h1, 3),
                             "P_K1": round(k1, 3), "P_K2": round(k2, 3), "P_verdict_approx": round(h1 * k1 * k2, 3)})
    return rows


def zero_event_bounds() -> List[dict]:
    rows = []
    for label, n in (("fraud groups, design A or B", 90), ("fraud cases, design A (ICC 0)", 180),
                     ("all groups", 270), ("all cases, design A (ICC 0)", 540), ("incomplete groups", 45),
                     ("genuine-but-informal groups (proposed quota)", 15)):
        rows.append({"population": label, "n_eff": n, "one_sided_95_upper_exact": stats.zero_event_upper(n),
                     "two_sided_wilson_upper": stats.wilson(0, n)[1]})
    return rows


def run_all(quick: bool = False) -> dict:
    scale = 0.1 if quick else 1.0
    return {"note": "Monte Carlo under stated generative assumptions; no evaluation data used.",
            "proportion_coverage": proportion_coverage(sims=max(100, int(2000 * scale))),
            "bootstrap_coverage": bootstrap_coverage(sims=max(40, int(400 * scale)), reps=max(100, int(400 * scale))),
            "paired_type1": paired_type1(sims=max(200, int(3000 * scale))),
            "paired_difference_coverage": paired_difference_coverage(sims=max(40, int(400 * scale)),
                                                                     reps=max(100, int(400 * scale))),
            "comparison_power": comparison_power(sims=max(150, int(1500 * scale))),
            "recall_operating_characteristics": recall_operating_characteristics(),
            "verdict_operating_characteristics": verdict_operating_characteristics(),
            "zero_event_bounds": zero_event_bounds()}


def summarise_coverage(rows: List[dict]) -> Dict[str, dict]:
    by_method = defaultdict(list)
    for row in rows:
        by_method[(row["design"].split("_")[0], row["method"])].append(row["coverage"])
    return {f"{design}|{method}": {"min": min(v), "mean": round(sum(v) / len(v), 4), "scenarios": len(v)}
            for (design, method), v in sorted(by_method.items())}


if __name__ == "__main__":
    print(json.dumps(run_all(quick=True), indent=1)[:2000])
