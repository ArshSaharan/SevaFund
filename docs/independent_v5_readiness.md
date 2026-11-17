# Independent evaluation v5 (hybrid v3): offline readiness report (revision 3)

**Date:** 2026-11-17.

**Constraints observed:**
- No API calls, no paid services and no cloud resources.
- No independent cases created or labelled.
- Nothing sealed.
- Frozen V3, hybrid v2, hybrid v3 and production are unchanged.
- Nothing pushed, merged or deployed.

**Documents.**
- Protocol: `evaluation/independent_test_protocol_v5.md`.
- Pre-registration: `evaluation/independent_test_v5/preregistration.json` (`v5-prereg-3`, PROPOSED). The success criteria and methods are owner-approved.
- Statistical methods, validation and acceptance bounds: `docs/independent_v5_statistical_methodology.md`.
- Recruitment checklist, effort and participant packets: `docs/independent_v5_recruitment.md`.

## A. Readiness checklist

| # | Item | Status |
|---|---|---|
| 1 | Hybrid v3 frozen as an evaluation candidate; freezes of hybrid v3, hybrid v2 and frozen V3 verify; benchmarks reproduce | Done (re-checked, §H) |
| 2 | Offline tooling (validator, exclusion registry, labelling, runner, scorer) | Done; approved earlier |
| 3 | Success criteria: H1 0.70, R1 0.80, K1 0.10, K2 0.50 (preliminary floor only), zero-tolerance gates G1–G5, fairness margin −0.10, ≥ 5 genuine-but-informal groups per category | **Approved** (A1–A6); snapshot recorded |
| 4 | Statistical methods: group-aware intervals, paired cluster comparisons, multiplicity rules | **Approved** (A7); validation re-run and reproduced exactly (§H) |
| 5 | Verdict scope: "not production readiness" printed in every score report | Done |
| 6 | Known-weakness commitment: G2 is never weakened, and the candidate is never modified to pass | Recorded in the pre-registration and protocol, and printed in the score report |
| 7 | Model availability and free-tier quota | **Not verified**; recorded as such (A8) |
| 8 | API calls and paid usage | **None authorised** (A9) |
| 9 | Participant packets: participants work without source code or earlier data | Done (`packet` command, tests) |
| 10 | Recruitment checklist and effort estimate for A and B | Done (`docs/independent_v5_recruitment.md`) |
| 11 | Pre-seal check, which `seal-kit` requires to pass | Done; run in §H. It currently reports 3 blocking items |
| 12 | Participants recruited, and feasibility shown | **Not started: needs you** |
| 13 | Design selected (A preferred, B resource-constrained) | Blocked on 12 |
| 14 | Pre-registration APPROVED and kit sealed | Blocked on 12, 13 and your authorisation |
| 15 | Independent cases, labels and API authorisations | Not started; not authorised |
| 16 | Login-test failure | Kept separate, documented only |

## B. Staffing and effort

Detail is in `docs/independent_v5_recruitment.md`. Hours below are with the 20% buffer.

| | Design A (preferred) | Design B (resource-constrained) |
|---|---|---|
| Total hours | ≈ 605 | ≈ 330 |
| Per author (4 authors) | ≈ 95 h | ≈ 54 h |
| Per labeller (2) | ≈ 86 h | ≈ 43 h |
| Adjudicator | ≈ 22 h | ≈ 11 h |
| Coordinator | ≈ 32 h | ≈ 17 h |
| Calendar at 4 h a week per person | ≈ 44–52 weeks | ≈ 23–28 weeks |

- **The per-case minutes are assumptions.** The 6-case pilot measures the real authoring time, and the feasibility check is re-run if it differs materially.
- **Recruit 4–5 authors** even for B, to allow for about 20% attrition.
- **Unknown availability.** Whether about 600 hours of independent effort can be found is the main open question. It is the reason the design is not selected yet.

## C. Approved success criteria (unchanged from revision 2, now owner-approved)

| Layer | Criterion | Threshold (95% interval, design-effect Wilson) |
|---|---|---|
| **Gates** (zero observed events) | G1: no provisional approval of an incomplete case | count = 0 |
| | **G2: no unsafe activation of any type**, including any fraud activation from collusive documents or cost-issuer-only fraud | count = 0 |
| | G3–G5: no Gemini-only rejection; provisional approval never treated as activation; no campaign-supplied confirmation accepted | count = 0 |
| **Primary endpoint** | H1: recall on dossier-detectable fraud | lower bound ≥ 0.70 |
| **Key secondary** | K1: false-positive rate | upper bound ≤ 0.10 |
| | K2: legitimate-complete approval, **a preliminary evaluation floor only** | lower bound ≥ 0.50 |
| **Verdict** | MEETS_MINIMUM_STANDARD only if every gate passes and H1, K1 and K2 are MET. **Not evidence of production readiness** | — |
| **Research target** | R1: dossier-detectable recall, assessed only if H1 is met | lower bound ≥ 0.80 |
| **Comparisons with hybrid v2** | 4 endpoints, Holm-adjusted cluster sign-flip test, and the interval must exclude 0 | — |
| **Fairness** | Legitimate-complete approval, v3 − v2 | lower bound > −0.10 |
| **Descriptive only** | Information requests, review, borderline, genuine-but-informal escalation, API reliability and latency | No claim from any single item |

**Pre-registered expectation and commitment.**
- The frozen workflow cannot independently verify the requested amount, so cost-issuer-only and collusive fraud may activate in the simulation and fail G2.
- If that happens, the report states that hybrid v3 failed the gate, with the cause of each activation.
- The gate is not changed, and the candidate is not modified.

## D. Statistical methodology (approved)

The full method is in `docs/independent_v5_statistical_methodology.md`.

**Intervals.** Kish design-effect Wilson with an ICC floor of 0.1.
- Worst coverage 0.9385 over 60 scenarios, against 0.81 for naive Wilson.
- n_eff is reported for every rate.

**Paired comparisons.** Cluster sign-flip test (type I error at most 0.039) and cluster-bootstrap intervals (coverage at least 0.9375).

**Multiplicity.**
- one primary endpoint;
- an intersection-union verdict;
- a fixed-sequence research target;
- a Holm family of 4 comparisons;
- everything else descriptive.

**Acceptance bounds for sealing** (methodology §9):
- primary coverage at least 0.935;
- bootstrap coverage at least 0.92;
- sign-flip type I error at most 0.05;
- paired-difference coverage at least 0.93;
- an exact reproduction of the committed validation record.

## E. Estimated API calls, time and cost (unchanged; nothing approved)

- **Design A:** at most 602 generation requests and 0 embedding requests.
- **Design B:** at most 305.
- **Free tier:** at 20 requests a day (**unverified**), at least 31 days for A and 16 for B.
- **Paid usage:** not approved.

## F. Remaining risks

1. **Recruitment.** About 600 hours (A) or 330 hours (B) of independent effort, over roughly 6–12 months at 4 hours a week. If it cannot be found, the evaluation cannot run as designed. C and D cannot support a safety verdict.
2. **G2 is likely to fail** because amounts are never confirmed. This would be an honest result about the candidate, not a defect in the evaluation.
3. **Verdict power.** A good system can still fail the all-components verdict by chance: 35–75% of the time in the lower reference scenario, mainly through K1.
4. **K2 is only a floor.** Meeting it says nothing about whether legitimate applicants are served well enough for production.
5. **Authoring usability.** Hand-written JSON may be hard for non-technical authors; the pilot tests this.
6. **Coordinator exposure,** if the coordinator is the developer.
7. **Unverified provider facts.** Model availability, quota and retirement dates are unverified.
8. **Carried forward:**
   - synthetic dossiers;
   - simulated confirmations;
   - retrieval that differs from production's embedding path;
   - free-tier-only results;
   - a test set that can be used once;
   - environment drift (guarded by the behavioural fingerprint).

## G. Remaining requirements for independent evaluation readiness

**Owner actions (in order):**
1. **Name a coordinator,** and decide whether participants are volunteers or compensated.
2. **Recruit** at least 3 (realistically 4–6) authors, 2 labellers and 1 adjudicator.
   - All must be independent and declared, each in one role.
   - Register them with pseudonymous codes and committed hours.
3. **Show feasibility:** `prepare_independent_data_v5.py feasibility REGISTRY` must report design A or B as feasible.
4. **Select the design:** A if feasible; B only if A is not; C or D only with explicit recorded approval.
5. **Provider facts:** confirm model availability and the free-tier quota in Google AI Studio, or keep them recorded as unverified planning assumptions. Either way, nothing is approved by it.
6. **Authorise** setting the pre-registration status to APPROVED, with the selected design recorded.

**Then, offline (with your authorisation):**

7. Run `run_independent_test_v5.py preseal-check --registry REGISTRY --out REPORT`. It must report no failures and nothing blocking.
8. Run `seal-kit --preseal-report REPORT`. It refuses unless the report passes for exactly the current kit files.

**After sealing (each step needs your go-ahead):**

9. Send author packets. Authors write the 6 pilot cases; check the authoring time and format usability.
10. Authors write the test cases. The coordinator validates and seals them.
11. Blind labelling, adjudication and label sealing.
12. A written API authorisation for the pilot (at most 8 requests), then a separate one for the main run.

## H. Final offline checks (2026-11-17)

**Pre-seal check.** `run_independent_test_v5.py preseal-check` ran as a complete check, including the statistics re-run and the tooling tests. The full report is `docs/independent_v5_preseal_check_2026-11-17.json`.

| Check | Result |
|---|---|
| Pre-registered criteria equal the owner's approval snapshot; the scorer implements all five G2 types | PASSED |
| Model availability and quota marked unverified; 0 approved requests; paid usage off; no substitution | PASSED |
| Statistical acceptance bounds: primary coverage 0.9385 (≥ 0.935); bootstrap 0.9275 (≥ 0.92); sign-flip type I 0.0387 (≤ 0.05); paired-difference coverage 0.9375 (≥ 0.93) | PASSED |
| Full Monte Carlo validation re-run, compared with the committed record | PASSED (identical in every section) |
| Tooling tests (`tests/test_independent_v5.py`, in a subprocess with no key) | PASSED (52 passed) |
| Freezes: hybrid v3 (fingerprint `2d117adb…40f8`), hybrid v2, frozen V3; production default `gemini-3.8-flash`; `app/` tree clean | PASSED |
| Exclusion registry (41 sources) | PASSED, with one expected warning: the test file changed since registration. Its old texts stay excluded by hash, and its current texts are excluded automatically |
| Participant packets for all three roles contain only allowlisted files | PASSED |
| No independent (`T5-`) case in any data file in the repository | PASSED |
| No network connection attempted (in-process socket guard) | PASSED (0 attempts; 0 API calls) |
| **Blocking** | Recruitment feasibility not shown (no registry); no design selected; status PROPOSED |
| **Ready to seal** | **No**, correctly: only the three owner-dependent items block |

**Other checks.**
- **Full test suite:** 479 passed, 1 failed. The failure is the known login test (`tests/test_campaigns.py::test_campaign_verification_endpoint`, documented separately).
- **Frozen benchmarks:** they reproduce (`check_frozen_benchmark_reproducibility.py`, `all_reproduced: true`). That covers the 300-, 200-, 150- and 100-case sets and the 10-case hybrid re-scoring.
- **No changes since the freeze (`e7b3688`):** no commits to `app/`, the datasets or the earlier runs.
- **Packet CLI:** builds outside the repository and refuses to build inside it.
- **Secret scan** of the 13 changed files: clean.
- **Nothing pushed or merged:** `origin` has only `main` at `d649f56`.
