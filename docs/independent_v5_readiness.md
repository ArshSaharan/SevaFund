# Independent evaluation v5 (hybrid v3): offline readiness report (revision 2)

**Date:** 2026-11-17.

**Constraints observed:**
- No API calls, no paid services and no cloud resources.
- No independent data collection.
- Nothing sealed.
- Production, frozen V3, hybrid v2 and the hybrid v3 freeze are unchanged.
- Nothing pushed, merged or deployed.

**Documents.**
- Protocol: `evaluation/independent_test_protocol_v5.md`.
- Pre-registration: `evaluation/independent_test_v5/preregistration.json` (`v5-prereg-2`, PROPOSED).
- Statistical methods and validation: `docs/independent_v5_statistical_methodology.md`.

## A. Readiness checklist

| # | Item | Status |
|---|---|---|
| 1 | Hybrid v3 frozen as an evaluation candidate; freeze, frozen V3, hybrid v2 and benchmark reproducibility verify | Done |
| 2 | Offline tooling (validator, exclusion registry, labelling, runner, scorer) approved by you | Done |
| 3 | Revised criteria: tiered recall (H1 0.70, R1 0.80); undetectable fraud descriptive; zero-tolerance G2 covering every unsafe activation, with upper bounds | Implemented; **needs your approval** |
| 4 | Interval method validated under clustering (Kish design effect, ICC floor 0.1; worst coverage 0.941); n_eff reported for every rate | Done |
| 5 | Multiplicity: one primary endpoint, intersection-union verdict, fixed-sequence research target, Holm family, clustered paired test (type I ≤ 0.039) | Done |
| 6 | Power documented with assumptions (simulated; replaces the earlier formula) | Done |
| 7 | Fairness: paired trade-off and ratio, non-inferiority margin, genuine-but-informal outcomes (quota raised to ≥ 5 groups per category) | Implemented; **margin and quota need approval** |
| 8 | Four stages (provisional → independent confirmation → final approval → activation) measured separately | Done |
| 9 | Retrieval difference from production's embedding path documented in the protocol, the pre-registration and every report | Done |
| 10 | Model availability and free-tier quota | **Not verified** (recorded as such everywhere) |
| 11 | Login-test failure kept separate | Done (documented only) |
| 12 | Recruitment feasibility shown (registry with committed hours) | **Not done: needs you** |
| 13 | Design chosen (A preferred) | Blocked on 12 |
| 14 | Pre-registration APPROVED and kit sealed | Blocked on 3, 7, 12, 13 and your approval |
| 15 | Independent cases, labels, and API authorisations | Not started; not authorised |

**Tests.**
- 45 offline tests of the evaluation tooling pass. They include reference values for every interval and test, the zero-tolerance gate failing on a collusive fraud, verdict logic, and feasibility.
- The full suite has the same single pre-existing login failure.

## B. Staffing requirements

**Roles and eligibility** (unchanged, D6):
- at least 3 authors (4–6 recommended), 2 labellers, 1 adjudicator and 1 coordinator;
- each signs the independence declaration;
- one role per person;
- no one involved in implementation or earlier benchmark tuning;
- you and the AI assistant are excluded.

**Hours.** Base figures are assumption-based; the "with buffer" figures add 20% for validator-driven revisions.

| | Design A (preferred) | Design B (fallback) |
|---|---|---|
| Authoring | 315 h (378 h) | 180 h (216 h) |
| Labelling | 144 h, i.e. 72 h per labeller (86 h each) | 72 h, i.e. 36 h per labeller (43 h each) |
| Adjudication | 18 h (22 h) | 9 h (11 h) |
| Coordination | 27 h (32 h) | 14 h (17 h) |
| Total | ≈ 504 h (≈ 605 h) | ≈ 275 h (≈ 330 h) |
| Example calendar: 4 authors at 4 h/week | ≈ 24 weeks of authoring | ≈ 14 weeks |
| Example calendar: 2 labellers at 4 h/week | ≈ 22 weeks | ≈ 11 weeks |

**Feasibility gate.**
1. Register candidates (pseudonymous codes) with `committed_hours`.
2. Run `python evaluation/prepare_independent_data_v5.py feasibility <registry.csv>`. It reports, for A and B, any shortfall in authors, labellers, the adjudicator or the coordinator.
3. You choose the design only after this passes.

**If the ~459 hours (authoring plus labelling) for A are unavailable: a realistic assessment of B.**

*What B keeps:*
- all 270 groups and every content quota;
- the same verdict probability as A when cases in a group are strongly correlated (0.25 or 0.82 in the two reference scenarios).

*What B costs:*
- paired power for a 10-point one-directional difference falls to 0.58–0.78, from 0.91–0.98 in A;
- no repeated presentations, so robustness cannot be studied;
- fraud zero-event bound of 3.3% rather than as low as 1.7%;
- genuine-but-informal cases fall from about 30 to 15.

*Attrition and rework.* Allow about 20% attrition: with 3 authors, losing one leaves B short. Recruiting 4–5 authors is the realistic minimum even for B.

*Below B.* C and D could not support a safety verdict (verdict probability 0.01–0.35). They need your explicit approval.

## C. Revised success criteria

| Layer | Criterion | Threshold (95% interval, design-effect Wilson) |
|---|---|---|
| **Gates** (zero observed events) | G1 no provisional approval of an incomplete case | count = 0 |
| | **G2 no unsafe activation of any type**: (a) fraud, (b) without final approval, (c) incomplete, (d) without a confirmation record, (e) via a campaign-supplied contact | count = 0 |
| | G3 no rejection from Gemini alone | count = 0 |
| | G4 provisional approval never treated as activation | count = 0 |
| | G5 no campaign-supplied confirmation accepted | count = 0 |
| **Primary endpoint** | H1: recall on dossier-detectable fraud (minimum safety threshold) | lower bound ≥ **0.70** |
| **Key secondary** | K1: false-positive rate | upper bound ≤ 0.10 |
| | K2: legitimate-complete approval | lower bound ≥ 0.50 |
| **Verdict** | MEETS_MINIMUM_STANDARD only if every gate passes and H1, K1 and K2 are MET | — |
| **Research target** | R1: dossier-detectable recall (only if H1 is met) | lower bound ≥ **0.80** |
| **Comparisons with hybrid v2** | Fraudulent provisional approvals; legitimate-complete approvals; dossier-detectable recall; FPR | Holm-adjusted cluster sign-flip p < 0.05 **and** interval excludes 0 |
| **Fairness** | Legitimate-complete approval, v3 − v2 (non-inferiority) | lower bound > −0.10 |
| **Descriptive only** | Information requests (avoidable ≤ 0.40, appropriate ≥ 0.70); non-fraud review ≤ 0.20; dossier-detectable fraud approved ≤ 0.10; borderline approved ≤ 0.15; genuine-but-informal escalation ≤ 0.10; API first-attempt ≥ 0.85, coverage ≥ 0.90, invalid ≤ 0.05, p95 latency ≤ 60 s | Reported; no claim from any single item |
| **Undetectable fraud** | Detected, provisionally approved, held and activated, by mechanism | Descriptive; its safety requirement is G2 |

**Zero ≠ zero.** Every gate reports a one-sided 95% upper bound, because zero observed events cannot establish a zero population rate. For example, zero unsafe activations among 90 fraud groups is compatible with a population rate of up to 3.3%. The bounds also apply only to the simulated confirmation process.

## D. Statistical methodology (summary)

The full detail and validation evidence are in `docs/independent_v5_statistical_methodology.md`.

**Correlation within groups.**
- Rates use a Wilson interval on n_eff = n / [1 + (m̃ − 1) · ICC]. The Kish cluster size m̃ is 2.25 for design A and 1 for B. ICC is floored at 0.1, and set to 1 when it cannot be estimated.
- In 48 clustered simulation scenarios, coverage was at least 0.941; naive Wilson fell to 0.81.

**Paired comparisons.**
- Exact cluster sign-flip test, equal to exact McNemar for one case per group.
- Type I error at most 0.039, where McNemar that ignores groups reached 0.075.
- Cluster-bootstrap intervals for differences, with coverage 0.938–0.948.

**Recall thresholds.**
- **0.70 minimum:** passes about 2% of the time if true recall is 0.70. A good system with true recall 0.85 passes 64–86% of the time; at 0.90, 92–99.5%.
- **0.80 research target:** needs true recall of about 0.90 or more (0.33–0.59 at 0.90; 0.81–0.98 at 0.95).
- **0.85:** would need true recall near 0.95.
- **The old 0.50:** passes 93% of the time even at true recall 0.75.

**Verdict power.** The verdict requires every component, so its power is roughly the product of theirs. For true recall 0.85, FPR 0.05 and approval 0.65, it is 0.25–0.65 in A. For 0.90, 0.03 and 0.75, it is 0.82–0.99. K1 is the binding component when the true FPR is near 5%.

**Paired power** (simulated; 90 groups per stratum; maximal clustering in A; two-sided; Holm worst case to unadjusted). For 10-point differences:

| Design | One-directional | Mixed |
|---|---|---|
| A | 0.91–0.98 | 0.55–0.74 |
| B | 0.58–0.78 | 0.29–0.52 |

The retrospective v2-to-v3 contrasts were larger (−16 and −25 points), but small recall or FPR differences are not detectable at this size.

## E. Estimated API calls, time and cost

These are unchanged, and **not approved**:
- Design A: at most 602 generation requests, 0 embedding requests.
- Design B: at most 305.
- Free tier: $0, at 20 requests a day (**unverified**), giving at least 31 days for A and 16 for B.
- Paid usage is not approved. For reference, design A would cost about $1–15 at the 2027 list price, plus thinking tokens.

## F. Operational risks and remaining limitations

**New or emphasised this round:**
1. **Verdict power.** A genuinely good system can still fail the conjunction verdict by chance, about 35–75% of the time in the lower reference scenario. This is the price of requiring every safety and fairness component at once.
2. **G2 is expected to be informative, not necessarily passed.** The frozen workflow does not confirm amounts, so fraud that only the cost issuer reveals, and collusive fraud, can activate in the simulation and fail G2. This is a correct finding about the candidate; the decomposition makes it visible.
3. **Under-powered subgroups.** Genuine-but-informal results are indicative only (18% upper bound with zero events at 15 groups). Small paired differences are undetectable.
4. **Labeller-dependent primary denominator.** If adjudicated dossier-detectable fraud falls below 36 groups, H1 is flagged as under-powered.
5. **Unverified provider facts.** Model availability, quota and possible retirement are unverified, and no substitution is allowed.

**Carried forward:**
- synthetic dossiers;
- simulated confirmations;
- retrieval that differs from production's embedding path;
- free-tier-only results;
- thresholds that are judgement calls;
- recruitment and authoring effort;
- coordinator exposure;
- single use of the test set;
- environment drift (guarded by the behavioural fingerprint).

## G. Decisions requiring your approval

1. **Fraud-recall tiers:** H1 minimum 0.70 and R1 research target 0.80. Alternatively an R1 of 0.85, which needs true recall near 0.95.
2. **Zero-tolerance G2 over all unsafe activations, including any fraud activation.**
   - Expect it to expose the frozen workflow's lack of amount confirmation.
   - Should authors be allowed to write collusive and cost-issuer-only fraud? I recommend yes, for realism.
3. **K1 at 0.10** (strict; about a 50% chance of MET when the true FPR is 5% under strong clustering) or 0.12. **K2 at 0.50.**
4. **Fairness non-inferiority margin of −10 points**, and the genuine-but-informal quota of at least 5 groups per category.
5. **Statistical methods:** Kish design-effect Wilson with ICC floor 0.1; cluster sign-flip test; Holm family of four; intersection-union verdict; fixed-sequence research target.
6. **Validator quota:** at least 50% of fraud groups per category intended to be detectable from the documents.
7. **Recruitment:** register candidates with committed hours and run the feasibility check. Then choose the design (A preferred; B only if A is infeasible; C or D only with explicit approval). Name the coordinator.
8. **Provider facts:** confirm model availability and free-tier quota yourself, or accept them as unverified planning assumptions.
9. After items 1–8: authorise me to set the pre-registration to APPROVED and seal the kit (offline).
10. Later and separately: written API authorisation for the pilot (≤ 8 requests), then for the main run.
