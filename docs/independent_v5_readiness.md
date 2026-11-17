# Independent evaluation v5 (hybrid v3): offline readiness report

**Date:** 2026-11-17

**Constraints observed:**
- No API calls, no paid usage and no cloud resources.
- Production, frozen V3, hybrid v2 and the hybrid v3 freeze are unchanged.
- Nothing pushed, merged or deployed.

The protocol is `evaluation/independent_test_protocol_v5.md`; the machine-readable pre-registration is `evaluation/independent_test_v5/preregistration.json` (status `PROPOSED`).

## A. Readiness checklist

| # | Item | Status |
|---|---|---|
| 1 | Hybrid v3 frozen as an evaluation candidate (`e7b3688`); freeze verifies, including the 750-case behavioural fingerprint | Done |
| 2 | Frozen V3 and hybrid v2 unchanged; frozen benchmarks reproduce | Done (re-verified) |
| 3 | Production untouched (`main` and `origin/main` at `d649f56`; branch never pushed; default model `gemini-3.8-flash`) | Done |
| 4 | Model fixed to `gemini-3.6-flash` with settings recorded; substitution refused by transport and pre-flight | Done |
| 5 | Model availability and quota confirmed *without* an API call | Partial: the committed log shows HTTP 200 for this model on 2026-11-16, and its model and pricing pages are published. The current quota can only be confirmed by you in AI Studio |
| 6 | Production retrieval reproduced offline (unchanged `retrieve_evidence`, no-embedding path); difference recorded; claims restricted | Done |
| 7 | Exclusion registry: 41 sources and 3,832 earlier texts (all 750 benchmark cases, development sets, historical, date-aware, test literals, examples, fixtures) | Done |
| 8 | Exact, near-duplicate and short-text duplicate protection; digit-normalised; across groups, within groups and against the pilot | Done, tested |
| 9 | Validator: schema, quotas, mechanisms, keyword-free lexicon check, independent date validation, participant eligibility, sealing | Done, tested |
| 10 | Labelling tools: blind copy, sheet checks, κ, adjudication with log, unresolved → borderline, sealing | Done, tested |
| 11 | Runner: offline plan, engineering dry run, budgeted audited transport, stopping rules, pause and resume without repeats, live path guarded | Done, tested offline. The live path has never been exercised, by design |
| 12 | Scorer: pre-registered metrics, intervals, gates, criteria, paired comparisons, trade-off; cannot import `app`; writes once | Done, tested |
| 13 | Engineering fixtures (ENG-), separate from and excluded from the independent test | Done |
| 14 | API-call, elapsed-time and cost estimate (section D) | Done |
| 15 | Login-test failure documented separately (`docs/known_issue_campaign_verification_test.md`) | Done; code not changed |
| 16 | **Success criteria approved** | **Waiting for you (G1)** |
| 17 | **Pre-registration set to APPROVED and kit sealed** (`run_independent_test_v5.py seal-kit`) | **Blocked on G1** |
| 18 | **Independent participants confirmed and registered** | **Not met: needs you (G2)** |
| 19 | Pilot and test cases authored, validated and sealed | Not started (needs 18) |
| 20 | Blind labels, adjudication and label seal | Not started (needs 19) |
| 21 | Written API authorisation for the pilot (≤ 8 requests) | Not given (G4) |
| 22 | Written API authorisation for the main run | Not given (G5) |

## B. Dataset recruitment requirements

**Roles.** No author or labeller may come from implementation or benchmark tuning.

| Role | Number | Notes |
|---|---|---|
| Authors | at least 3 (4–6 recommended) | Mix of backgrounds, for example a medical social worker or hospital billing staff, a school or college administrator, NGO or community-project staff |
| Labellers | 2 | Similar background to the authors; none of them authors |
| Adjudicator | 1 | A senior person in one of those fields |
| Coordinator | 1 | Ideally not the developer. If it is the developer, they validate, seal and run only, and read no case before scoring |

**Eligibility.** Each author, labeller and adjudicator signs `INDEPENDENCE_DECLARATION.md`. They must answer "no" to:
- involvement in implementation;
- involvement in prior benchmarks or tuning;
- having seen the verifier code or lexicons;
- having seen prior corpora.

They hold one role only. The validator enforces this from the pseudonymous registry; real identities stay outside the repository. The developer and the AI assistant are excluded by rule.

**Materials given to participants.**
- **Authors:** `AUTHORING_GUIDE.md`, `REQUIRED_EVIDENCE_POLICY.md` and `example_case.json`. Nothing else: no code, no protocol and no earlier data.
- **Labellers:** the blinded copy, `LABELLING_GUIDE.md` and the policy.

**Skills.**
- Familiarity with Indian medical, education or community fundraising documents.
- At least one author able to write regional-language headings.

**Workload.** Effort is assumption-based (30 min per case and 10 min per group to author, 8 min per case per labeller):

| Design | Authoring | Labelling | Adjudication | Coordination |
|---|---|---|---|---|
| A | ~315 h | ~144 h | ~18 h | ~27 h |
| B | ~180 h | ~72 h | ~9 h | ~14 h |

**Content each author set must cover.** The validator rejects a set that misses any of these:
- every fraud mechanism;
- the incomplete subtypes, including "genuine but informal";
- date-sensitive cases;
- long dossiers;
- keyword-free fraud;
- 1–3 genuinely different cases per group.

**Ethics.** If participants are recruited through a university, check whether the institution requires ethics or consent paperwork for participant contributions.

## C. Final metrics and success criteria (pre-registered; thresholds need approval)

**Population and intervals.** Intent-to-treat is primary. 95% intervals use a design-effect-adjusted Wilson interval, with a cluster bootstrap over scenario groups as secondary.

**Detection.** FLAG_FOR_REVIEW or REJECTED only. Provisional approval is never counted as activation.

| Metric | Definition (hybrid v3) | Success criterion |
|---|---|---|
| Fraud recall | Detected ÷ fraudulent; also on dossier-detectable fraud | C1: dossier-detectable recall, lower bound ≥ 0.50 |
| Fraud precision | Detected fraud ÷ (detected fraud + detected legitimate) | C2: lower bound ≥ 0.70 |
| False-positive rate | Detected ÷ legitimate (complete + incomplete) | C3: upper bound ≤ 0.10 |
| Legitimate approval rate | APPROVED ÷ legitimate-complete | C4: lower bound ≥ 0.50 |
| Information-request rate | NMI ÷ cases; avoidable (L) and appropriate (I) | C5: L upper bound ≤ 0.40; C5b: I lower bound ≥ 0.70 |
| Manual-review rate | FLAG ÷ cases; by review basis; non-fraud | C6: non-fraud upper bound ≤ 0.20 |
| Unsafe provisional approvals | APPROVED among incomplete, fraud, dossier-detectable fraud and borderline | Gate G1: incomplete = 0. C7: dossier-detectable fraud upper bound ≤ 0.10. C7b: borderline upper bound ≤ 0.15 |
| Unsafe activations | VERIFIED_ACTIVE (simulated) for fraud (a); with an unconfirmed check (b); incomplete (c); without a confirmation record (d); via a campaign-supplied contact (e) | Gate G2: b–e = 0. C8: fraud activation upper bound ≤ 0.10 |
| Independent-confirmation failures (simulated) | Fraud passing confirmation; legitimate cases blocked at confirmation; campaign-supplied confirmations accepted; amount-check outcomes | Gate G5: accepted = 0. The others are reported with intervals |
| API reliability | First-attempt success; valid-answer coverage; invalid outputs; failure categories; retries; quota pauses; model versions; tokens | C10: lower bound ≥ 0.85. C10b: lower bound ≥ 0.90. C10c: upper bound ≤ 0.05 |
| Latency | HTTP-only median, p90, p95 and max (bootstrap intervals); timeouts | C11: p95 ≤ 60 s |
| Other gates | G3: no rejection from Gemini alone. G4: provisional approval never treated as activation | Must be 0 |

**Judgement rule.**
- **MET:** the bound clears the threshold.
- **INCONCLUSIVE:** the point estimate clears it, the bound does not.
- **NOT_MET:** the point estimate does not.

Gates pass only with zero events. There is no composite score.

**Paired comparison (hybrid v3 against hybrid v2, same Gemini answers, case level).** Covers recall, FPR, legitimate approval and unsafe provisional approval, using an exact McNemar test with Holm adjustment and a cluster-bootstrap interval of the difference. A difference is claimed only if both are significant.

**Trade-off.** For each system: fraud detected, held, provisionally approved and activated, against legitimate applicants approved, delayed, flagged and activated. It also reports extra legitimate delays per extra fraud detected, and rates per 1,000 campaigns at 2%, 5% and 10% fraud prevalence.

## D. Estimated API calls, elapsed time and cost

**Requests** = N + ⌈0.10 N⌉ retries + 8 pilot, with 0 embedding requests. On the free tier, about 20 requests a day were observed.

| Design | Cases | Max requests | Free-tier days (min) | Paid estimate at 2027 list price (reference only; not approved) |
|---|---|---|---|---|
| A: preferred (270 groups, ≤ 540 cases) | ≤ 540 | 602 | 31 | ~$1–5 input + ≤ $9.25 visible output + ~$4.50 per 1,000 thinking tokens per request |
| B: 270 groups × 1 case | 270 | 305 | 16 | about half of A |
| C: 150 groups × 1 (reduced) | 150 | 173 | 9 | — |
| D: 90 groups × 1 (minimal) | 90 | 107 | 6 | — |

**Free tier.** The API cost is $0. Time is the cost, and only synthetic data may be sent.

**Prices.** The published standard price from 2027-01-01 is $1.50 per million input tokens and $7.50 per million output tokens, with thinking counted as output. The introductory price until 2026-12-31 is $0.75 / $3.75. Source: <https://ai.google.dev/gemini-api/docs/pricing>.

**Tokens.**
- Input is estimated at about 4 characters per token: a fixture mean of about 920 tokens per prompt, and a bound of about 5,900.
- Thinking tokens are unknown until measured, and are logged per request.

**Precision and power by design** (protocol §9):

| Design | Recall ± (points) | Zero-event upper bound | Paired power for a 10-point difference |
|---|---|---|---|
| A | 7–10 | 4–8% | 0.86 (fraud) |
| B | 10 | 7.9% | 0.57 |
| C | 14 | 11.4% | 0.32 |
| D | 17 | 20.4% | 0.23 |

C and D are explicitly weaker designs.

## E. Operational risks

1. **Free-tier quota and duration.** About 20 requests a day means at least 31 days for design A, and longer with pauses. The quota is shared with any other use of the same key.
2. **Free-tier reliability.** The last live run returned 1 valid answer in 4 requests. The approved transient-failure rules (25% cumulative, or the retry allowance used up) could end the run early. The partial results would be reported, and the sealed test set would be spent.
3. **Model lifecycle.** The provider now lists newer Flash models, so `gemini-3.6-flash` could change or be retired during a month-long run.
   - Mitigations: `modelVersion` logging, segmented reporting, and the 45-day calendar limit.
   - No substitution is allowed, so a retirement ends the run.
4. **Free-tier data terms.** Prompts may be used by the provider, so only synthetic cases may be sent; the runner enforces this.
5. **Recruitment and authoring time.** About 500 person-hours for design A. Validator rejections (quotas, duplicates, dates) will need revision rounds.
6. **Label quality.** Low κ on borderline and documentation judgements. Unresolved cases become borderline, which weakens the primary metrics.
7. **Coordinator exposure.** If the developer coordinates, there is a risk of seeing cases or labels before scoring. Mitigations: blind workflow, hash-only label checks in the runner, and counters-only status.
8. **Single use.** A defect found mid-run in the *system* cannot be fixed under this freeze. A defect in the *runner* is caught by the pilot first.
9. **Kit brittleness.** The kit seal hashes the tooling, tests and fixtures. Any later edit invalidates live runs until re-sealed, which is allowed only before test cases exist.
10. **Environment drift.** A Python or package upgrade could change frozen behaviour. The freeze check recomputes the 750-case behavioural fingerprint at every start and refuses on any change.
11. **Long-running local process.** Runs are resumable, and pauses persist on disk. Resumption is manual, with no background scheduling.

## F. Remaining limitations

- **Synthetic dossiers.** The cases are author-written; real documents (scans, OCR, regional languages, insider fraud) may behave differently.
- **Simulated confirmation and amount checks.** They assume an honest verifier and honest independent sources. They are never real-world verification.
- **Retrieval.** Production's no-embedding fallback, not its embedding path. Results do not represent the exact production pipeline.
- **Model.** Results apply to `gemini-3.6-flash` on the free tier only, not to production's `gemini-3.8-flash`, which was unreliable in earlier probes. Free-tier latency and reliability do not represent a paid tier.
- **Thresholds.** The success thresholds and the system's own thresholds are reasoned judgements, not calibrated.
- **Power.** Paired comparisons have limited power below design A. Group clustering widens every interval.
- **Prevalence re-weighting** assumes per-stratum rates transfer to real prevalence.
- **Validator limits.** It checks structure, quotas, duplicates and dates, not realism. Duplicate thresholds may force some legitimate rephrasing.
- **Engineering fixtures.** Written by the assistant, they demonstrate that the tooling works and are not evidence about the system. The live API path has never run.
- **Known hybrid v3 limitations.** 13 are recorded in the freeze manifest, for example insider fraud, the palatoplasty lexicon gap and the information-request burden.

## G. Decisions requiring your approval

1. **G1 – Success criteria.** Approve or edit thresholds C1–C11 and gates G1–G5 (section C). After that I set the pre-registration to APPROVED and seal the kit (offline, no API).
2. **G2 – Participants and design.** Confirm that at least 3 independent authors, 2 labellers and 1 adjudicator are actually available, and say who coordinates. Choose a design:
   - A is preferred;
   - B gives the same group-level precision for half the effort but less paired power;
   - C and D are explicitly weaker.
3. **G3 – Model quota.** Check the current `gemini-3.6-flash` free-tier quota in Google AI Studio yourself, or tell me to treat 20 a day as the planning figure. No call is needed from me.
4. **G4 – Pilot.** Later, when pilot cases exist: a written authorisation for ≤ 8 free-tier requests.
5. **G5 – Main run.** Later, after the pilot review: a separate written authorisation for the main run (for example ≤ 594 requests for design A, free tier only).
6. **G6 – Ethics paperwork.** Whether any is required for the participants.
7. **G7 – Login test.** Optional: fix the failing test as a separate, approved change. It is documented, not fixed.
