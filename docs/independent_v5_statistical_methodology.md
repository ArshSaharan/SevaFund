# v5 independent evaluation: statistical methodology and validation

**Status (2026-11-17).**
- Pre-registration `v5-prereg-2` is PROPOSED, not sealed.
- No independent data exists, and no API call was made.
- Every number below comes from offline Monte Carlo or exact binomial calculations. The full record is `evaluation/independent_test_v5/statistical_validation.json`, reproducible with `python evaluation/run_independent_test_v5.py validate-statistics`. The validator was seeded and used no evaluation data.

## 1. Unit of analysis and correlation

- **Clustering.** Cases are clustered in scenario groups: one author, one situation, and 1–3 cases. Cases in a group share their author, wording habits and situation, so they are positively correlated.
- **Unit.** Every rate is estimated at case level, and its uncertainty is computed for the clustered design.
- **Paired comparisons** are also case level (owner decision D4), with tests and intervals that respect the clustering.

## 2. Confidence intervals

**Primary interval (all proportions, including precision).**
- A Wilson score interval on the effective sample size n_eff = n / DEFF.
- DEFF = 1 + (m̃ − 1) · ICC.
  - m̃ = Σ m_i² / n is Kish's size-weighted cluster size, which is exact for unequal group sizes.
  - ICC is the one-way ANOVA intraclass correlation over scenario groups. It is floored at 0.10 and capped at 1, and set to 1 when it cannot be estimated (no within-group replication or no variation, for example zero events).
- **Design A:** groups of 1, 2 and 3 cases in proportion 1:2:1 give m̃ = 2.25. DEFF therefore lies between 1.125 (ICC at the floor) and 2.25 (ICC = 1), and n_eff between 0.44n and 0.89n.
- **Design B:** one case per group, so DEFF = 1 and n_eff = n.
- **Reporting.** Every reported rate carries n, groups, m̃, the ICC estimate, the ICC used, DEFF and n_eff.

**Secondary intervals.**
- A cluster bootstrap over scenario groups (percentile, 5,000 replications, fixed seed).
- A group-level majority-vote Wilson interval.

**Zero-event bound.** The exact one-sided 95% upper bound is 1 − 0.05^(1/n_eff), with ICC = 1 when there are no events.

**Coverage under clustering.** 2,000 simulations per scenario, Monte Carlo standard error about ±0.005.
- **Clustered scenarios (48):** 45 or 90 groups of 1–3 cases; true rate 0.05–0.95; ICC 0–0.9.
- **Unclustered scenarios (12).**

| Method | Clustered: worst coverage | Clustered: mean | Unclustered: worst / mean | Mean width (clustered) |
|---|---|---|---|---|
| Naive Wilson (ignores groups) | **0.810** | 0.886 | 0.939 / 0.958 | — |
| Design effect, mean group size | 0.929 | 0.946 | 0.939 / 0.958 | — |
| Design effect, Kish size | 0.936 | 0.952 | 0.939 / 0.958 | 0.151 |
| **Design effect, Kish size, ICC floor 0.1 (chosen)** | **0.941** | **0.955** | 0.939 / 0.958 | 0.153 |
| Wilson on the number of groups | 0.940 | 0.972 | 0.939 / 0.958 | 0.172 |
| Cluster bootstrap (6 scenarios, 400 simulations each) | 0.928 | 0.942 | — | — |

**Conclusions.**
- Ignoring the groups would overstate precision badly, with coverage as low as 81%.
- The chosen method never fell below 0.94 in any clustered scenario. Its unclustered minimum (0.939) is the Wilson interval's own discreteness at extreme rates, not a clustering effect.
- The floor costs about 1% in width. Counting groups instead is safe but about 13% wider.
- The paired-difference bootstrap covered 0.938–0.948 in three tested scenarios.

## 3. Paired comparisons with hybrid v2

**Test: an exact cluster sign-flip randomisation test.**
- For each group, d_k = (pairs where only hybrid v3 has the outcome) − (pairs where only hybrid v2 has it).
- The null distribution of Σd_k comes from flipping the sign of each group's d_k, enumerated exactly.
- With one case per group, this is exactly the two-sided exact McNemar test; a test confirms this.

**False-positive rate (type I error) at α = 0.05.** 3,000 simulations per scenario; 90 groups of 1–3 cases. Within a group, discordant pairs agree in direction with probability κ.

| Discordance | κ | Exact McNemar ignoring groups | Cluster sign-flip |
|---|---|---|---|
| 0.10 | 0.5 / 0.8 / 1.0 | 0.034 / 0.040 / 0.034 | 0.029 / 0.032 / 0.025 |
| 0.30 | 0.5 / 0.8 / 1.0 | **0.065 / 0.063 / 0.075** | 0.038 / 0.035 / 0.039 |

The ordinary McNemar test rejects too often when discordance clusters; the sign-flip test stays below 0.05.

**Multiplicity.** The family has four comparisons:
- fraudulent provisional approvals;
- legitimate-complete approvals;
- recall on dossier-detectable fraud;
- false-positive rate.

They are adjusted with Holm. A difference is claimed only if the Holm-adjusted p < 0.05 **and** the cluster-bootstrap 95% interval of the difference excludes 0. Unadjusted p-values are shown but never support a claim.

**Power assumptions.**
- 90 groups per compared stratum: design A is about 180 cases in groups of 1–3; design B is 90 single cases. C is 45 groups and D is 30.
- Two-sided test.
- In design A, every discordant pair within a group points the same way (κ = 1, maximal clustering; conservative).
- "One-directional" effects: discordance = difference + 0.02, as when one system is uniformly stricter. "Mixed" effects: discordance = difference + 0.10.
- Power is shown unadjusted (α = 0.05) and at Holm's worst case (α/4 = 0.0125, the first Holm step). Real Holm power lies between the two.
- 1,500 simulations per cell.

| True difference | A one-dir. | A mixed | B one-dir. | B mixed | C one-dir. | D one-dir. |
|---|---|---|---|---|---|---|
| 5 points | 0.65 / 0.41 | 0.29 / 0.13 | 0.26 / 0.10 | 0.15 / 0.05 | 0.04 / 0.01 | 0.01 / 0.00 |
| 10 points | 0.98 / 0.91 | 0.74 / 0.55 | 0.78 / 0.58 | 0.52 / 0.29 | 0.29 / 0.08 | 0.09 / 0.02 |
| 15 points | 1.00 / 1.00 | 0.95 / 0.87 | 0.97 / 0.90 | 0.78 / 0.59 | 0.61 / 0.33 | 0.26 / 0.08 |
| 25 points | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 0.99 / 0.95 | 0.95 / 0.84 | 0.72 / 0.45 |

(Each cell is unadjusted / Holm worst case.)

**Expected effect sizes.**
- The retrospective in-sample contrast between hybrid v2 and hybrid v3 was large and one-directional:
  - fraudulent provisional approvals 64 → 20 of 280 (−15.7 points);
  - legitimate approvals 231 → 162 of 280 (−24.6 points), under a clean-Gemini assumption.
- Effects of that size would be detected with power of at least 0.9 in A and B.
- The legitimate-*complete* effect may be smaller. Recall and false-positive differences are expected to be small, and the design has little power for them, so "no supported difference" there is **not** evidence of equivalence.

## 4. Fraud-recall thresholds (item 1)

**Primary endpoint H1.** Recall of hybrid v3 on fraud the labellers judged detectable from the submitted documents (intent-to-treat), with a 95% lower bound ≥ 0.70. This is a one-sided test of "recall ≤ 0.70" at α = 0.025.

**Research target R1.** A 95% lower bound ≥ 0.80. It is assessed only if H1 is met (fixed sequence, so no extra error).

**Not detectable from documents.** Fraud of this kind (consistent fabrication, independent-record contradictions, collusive payees) is **reported descriptively by mechanism, with no threshold.** It is stopped, if at all, by independent confirmation, which gate G2 governs.

**Expected size.** Authors must make at least 50% of fraud groups intended to be detectable, so H1 has about 45 groups. That is n_eff 45–80 in A (depending on clustering) and 45 in B. If fewer than 36 adjudicated groups result, H1 is reported as under-powered.

**Minimum observed recall needed to clear the bound:**

| n_eff | T = 0.50 (old) | T = 0.70 (minimum) | T = 0.80 (research) | T = 0.85 |
|---|---|---|---|---|
| 45 | 0.667 | 0.844 | 0.933 | 0.956 |
| 80 | 0.613 | 0.812 | 0.900 | 0.938 |

**Probability the bound clears the threshold, by true recall** (n_eff 45 / 80):

| True recall | T = 0.50 | T = 0.70 | T = 0.80 | T = 0.85 |
|---|---|---|---|---|
| 0.70 | 0.75 / 0.96 | **0.02 / 0.02** (type I) | 0 / 0 | 0 / 0 |
| 0.75 | 0.93 / 1.00 | 0.09 / 0.12 | 0.00 / 0.00 | 0 / 0 |
| 0.80 | 0.99 / 1.00 | 0.30 / 0.46 | 0.01 / 0.01 | 0.00 / 0.00 |
| 0.85 | 1.00 / 1.00 | 0.64 / 0.86 | 0.08 / 0.13 | 0.03 / 0.01 |
| 0.90 | 1.00 / 1.00 | 0.92 / 0.995 | 0.33 / 0.59 | 0.16 / 0.18 |
| 0.95 | 1.00 / 1.00 | 1.00 / 1.00 | 0.81 / 0.98 | 0.61 / 0.79 |

**Consequences.**
- **The old 0.50 threshold** would usually be met by a system that misses a quarter of detectable fraud.
- **The 0.70 minimum** keeps the false pass rate near 2% when true recall is only 0.70. A good system (true recall 0.85) passes with probability 0.64 (B, or A with strong clustering) to 0.86 (A, weak clustering).
- **The 0.80 research target** is realistic only if true recall is about 0.90 or more.
- **A 0.85 target** would need true recall near 0.95, and failing it would say little.

## 5. Unsafe activations: zero tolerance (item 2)

**The four stages are measured separately:**

| Stage | Definition | Measured as |
|---|---|---|
| Provisional approval | Automated APPROVED → ELIGIBLE_PENDING_CONFIRMATION; authenticity unconfirmed; nothing public; no money | S1 |
| Independent confirmation | Each required check (beneficiary, institution, payee) recorded as CONFIRMED through an independently sourced contact | S2 (checks confirmed per case) |
| Final approval | All three required checks independently CONFIRMED, none pending | S3 |
| Campaign activation | Workflow state VERIFIED_ACTIVE: live and disbursement-eligible | S4 |

- In the frozen workflow, S3 and S4 should coincide.
- **S4 without S3** counts as an unsafe activation.
- **S3 without S4** counts as a workflow defect.

**Gate G2 (zero tolerance, observed).** No unsafe activation of any type:
- (a) a fraudulent case;
- (b) without final approval;
- (c) an incomplete case;
- (d) without a confirmation record;
- (e) through a campaign-supplied contact.

**Why zero observed events are not zero risk.** Each gate reports the exact one-sided 95% upper bound:

| Population | n_eff | Upper bound with zero events |
|---|---|---|
| Fraud groups (A or B) | 90 | 3.3% |
| Fraud cases (A, no correlation) | 180 | 1.7% |
| All groups | 270 | 1.1% |
| All cases (A, no correlation) | 540 | 0.55% |
| Incomplete groups | 45 | 6.4% |
| Genuine-but-informal groups | 15 | 18.1% |

These bounds apply to the *simulated* confirmation process only, which assumes honest independent parties and a careful verifier. Verifier error, social engineering and compromised directories are explored only in the separate sensitivity simulation.

**Pre-registered expectation.** The frozen workflow does not confirm amounts. Fraud that only the cost issuer would reveal, such as undisclosed insurance cover, can reach activation in the simulation and fail G2. Collusive fraud that no independent party reveals can as well. The report splits every fraud activation into those two causes and shows whether the simulated amount check (Appendix A) would have caught it.

## 6. What decides the verdict (items 3–4)

| Layer | Content | Error control |
|---|---|---|
| Safety gates G1–G5 | Zero observed events | Not hypothesis tests; any event fails. Upper bounds reported |
| Primary endpoint H1 | Dossier-detectable fraud recall, lower bound ≥ 0.70 | One-sided α 0.025 |
| Key secondary K1, K2 | FPR upper bound ≤ 0.10; legitimate-complete approval lower bound ≥ 0.50 | — |
| Verdict | MEETS_MINIMUM_STANDARD only if every gate passes and H1, K1 and K2 are MET | Intersection-union: requires every component, so no adjustment is needed |
| Research target R1 | Lower bound ≥ 0.80 | Fixed sequence after H1 |
| Comparisons with hybrid v2 | 4 tests | Holm, plus a bootstrap interval that excludes 0 |
| Fairness non-inferiority | Legitimate-complete approval, v3 − v2, lower bound > −0.10 | A single pre-specified assessment |
| Everything else | About 11 descriptive benchmarks and all other metrics | No claim from any single item |

**Power of the verdict.** Because the verdict needs every component, its probability is roughly the product of theirs (exact binomial per component, components treated as independent):

| Design | True recall 0.85, FPR 0.05, legitimate approval 0.65 | True recall 0.90, FPR 0.03, legitimate approval 0.75 |
|---|---|---|
| A (strong to weak clustering) | 0.25 – 0.65 | 0.82 – 0.99 |
| B | 0.25 | 0.82 |
| C | 0.04 | 0.35 |
| D | 0.01 | 0.11 |

K1 is the most demanding component when the true FPR is near 5%. With strong clustering, the probability its bound clears 0.10 is about 0.49 in A and B. This is a deliberate safety-versus-power trade-off to approve or adjust (readiness report, G).

## 7. Legitimate-applicant fairness (item 5)

- **Trade-off.** For each system: fraud detected, held, provisionally approved, finally approved and activated, against legitimate applicants approved, delayed, flagged, errored and activated. The paired change from hybrid v2 to v3 is shown for fraudulent provisional approvals and for legitimate-complete approvals. It also reports legitimate approvals lost per fraudulent approval prevented, with a bootstrap interval reported only when the prevented count's interval excludes 0. The retrospective 64 → 20 / 231 → 162 contrast is quoted as context only.
- **Non-inferiority.** Hybrid v3's legitimate-complete approval rate must not be more than 10 points below hybrid v2's (95% lower bound of the paired difference > −0.10).
- **Genuine beneficiaries without formal quotations.** At least 5 groups per category (15 overall; about 30 cases in A, 15 in B):
  - approval, information request, flag, rejection and error rates;
  - an *inappropriate escalation* rate (flag or reject), with a descriptive benchmark of ≤ 0.10 upper bound;
  - the share resolvable through the simulated assisted route (the cost issuer would state an amount covering the goal).

  With 15 groups, zero escalations still leave an 18% upper bound. These results are indicative, not conclusive.
- **Group comparisons.** Legitimate approval and information-request rates by category and by beneficiary type, with the lowest-to-highest ratio. Below 0.8 is flagged for screening only.

## 8. Reproducibility

- **Seeds:** order 20261117, bootstrap 20261116, validation 20261118–20261122.
- **Implementation:** `evaluation/independent_v5/stats.py`, `scorer.py` and `ci_validation.py`.
- **Reference-value tests:**
  - Wilson: 0/10 and 3/10 against published values;
  - a hand-computed ANOVA ICC;
  - the Kish size;
  - the zero-event bound;
  - the sign-flip test against exact McNemar for singleton groups, plus a hand-enumerated clustered case.

  These are in `tests/test_independent_v5.py`.
