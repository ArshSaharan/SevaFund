# Independent evaluation protocol v5: hybrid v3

**Status (2026-11-17)**

| Item | State |
|---|---|
| Tooling | Built and tested offline |
| Success criteria and statistical methods | **Approved by the owner** (2026-11-17, A1–A9 in §2) |
| Protocol, pre-registration and kit | Not sealed |
| Independent cases | None exist yet; none may be created or labelled yet |
| Independent participants | **Not confirmed**; recruitment feasibility must be shown before the design is chosen |
| Design | **Not selected** (A preferred; B the resource-constrained alternative) |
| Model availability and free-tier quota | **Not verified** |
| API calls | 0 made. 0 approved for this evaluation |

- The owner's decisions D1–D11, the second-review refinements R1–R10 and the criteria approval A1–A9 are recorded in §2.
- The machine-readable pre-registration is `independent_test_v5/preregistration.json`, version `v5-prereg-3`, status `PROPOSED`. It holds every definition, threshold and parameter used by the tools, and a snapshot of the approved criteria that the pre-seal check compares against.
- The statistical methods and their validation are in `docs/independent_v5_statistical_methodology.md`.
- Recruitment, effort and participant packets are in `docs/independent_v5_recruitment.md`.
- Nothing runs live until the remaining requirements in §13 are met and the owner gives a separate written API authorisation.
- This protocol supersedes `independent_test_protocol_v4.md` for hybrid v3. v4 was prepared for hybrid v2 and never executed.

## 1. System under test

| Item | Value |
|---|---|
| Candidate | hybrid v3, policy `hybrid-v3-dev-1`, settings digest `a01273d9e3c89b0e`. Frozen as a development evaluation candidate only |
| Freeze | `evaluation/hybrid_v3_freeze.json`, commit `e7b3688`, behavioural fingerprint `2d117adb…40f8`. Check with `python evaluation/freeze_hybrid_v3.py verify` |
| Frozen dependencies | frozen V3 (`1c7e739`) and hybrid v2 (`b9f7514`), both verified at every run start |
| Model | `gemini-3.6-flash` exactly. The runner passes this ID explicitly, refuses any other model in the request URL, and refuses to start if `GEMINI_MODEL` names another model. No substitution is allowed |
| Generation settings | temperature 0.1; JSON output with the frozen schema; 2,048 max output tokens; timeouts 10/180/20/10 s; one HTTP request per client call |
| Prompt | frozen hybrid-v2 date-aware prompt (rendered-prompt fingerprint in the freeze manifest) |
| Production | unchanged. The default stays `gemini-3.8-flash`, and nothing in production imports the evaluation code |

**Model availability (D1, R9): not verified.** The evidence available without an API call:
- The committed request log shows that `gemini-3.6-flash` was accepted with HTTP 200 on 2026-11-16 at 20:26 UTC.
- Later requests failed with SERVER_ERROR and QUOTA_EXHAUSTED, never MODEL_NOT_FOUND.
- The model page and pricing table are published at ai.google.dev.
- Current availability and quota can only be confirmed by the owner in Google AI Studio, or by an approved call. The runner records the provider's `modelVersion` for every request, and reports a change mid-run as two segments.

## 2. Decisions recorded

| ID | Owner's decision | How it is implemented |
|---|---|---|
| D1 | Gemini 3.6 Flash, verified without API calls; production stays on 3.8 Flash; no silent substitution | §1. Model fixed in the pre-registration; transport and pre-flight refuse other models |
| D2 | 602 calls **not** approved; no paid usage; the earlier 10-call approval does not carry over; prepare offline | No authorisation file exists. `api_usage.approved_requests = 0`, `paid_usage_allowed = false`. Estimates in §9 |
| D3 | Reproduce production retrieval where possible without API calls; record any difference | §6. Production `retrieve_evidence` is called unchanged on its no-embedding path. The difference from the embedding path is recorded, and claims are restricted |
| D4 | Compare frozen hybrid v2 and hybrid v3 on the same Gemini responses; paired, case level | §7. One answer per case is scored by both, plus V3 alone. Exact cluster sign-flip test (equal to exact McNemar for one case per group), cluster-bootstrap intervals, Holm adjustment |
| D5 | Amount confirmation stays a pre-registered simulation, measured separately, never claimed as real | §6 step 7 and M9d. Every output is labelled "SIMULATED … not real-world verification" |
| D6 | Independent authorship and blind labelling approved; confirm participants exist; exclude anyone involved | §3. Participant registry, signed declarations and automated eligibility checks. **Availability not yet confirmed** |
| D7 | Keep the 270-group design as preferred; do not execute; give usage, time and cost; propose an explicitly weaker alternative if needed | §9. Four designs with intervals and power |
| D8 | Use each scenario's submission date; validate date-sensitive scenarios independently | §4. `submitted_on` is "today". Authors declare `date_facts`; an independent parser checks them; labellers record `date_check` |
| D9 | Pre-register definitions and success criteria with intervals; report the fraud-versus-delay trade-off; provisional ≠ activation | §7. Numeric thresholds are **proposed** and need approval before sealing |
| D10 | Any post-freeze change creates a separately versioned candidate | Freeze rule. Appendix procedures A and B are not in this candidate |
| D11 | Operational stopping rules; never stop on accuracy; no label inspection during execution | §10. The runner never parses labels (hash check only); interim status shows counters only |

**Second-review refinements (owner, 2026-11-17)**

| ID | Refinement | How it is implemented |
|---|---|---|
| R1 | The 0.50 recall bound is too permissive; give a minimum, a research target and descriptive reporting for undetectable fraud | Primary endpoint H1: lower bound ≥ 0.70. Research target R1: ≥ 0.80, only after H1. Non-dossier-detectable fraud reported descriptively. Operating characteristics in the methodology document, §4 |
| R2 | Unsafe activations are a zero-tolerance gate; separate the four stages; zero ≠ zero rate | Gate G2 covers types (a)–(e), including any fraud activation. Stages S1–S4 measured separately (§8). One-sided upper bounds are reported for every gate |
| R3 | Validate the intervals; account for clustering; document the method and effective sample size | Kish design-effect Wilson with ICC floor 0.1, validated by Monte Carlo (worst coverage 0.941 against 0.810 for naive Wilson). n_eff is reported for every rate |
| R4 | Multiple testing and power | One primary endpoint. Intersection-union verdict; fixed-sequence research target; Holm family for comparisons; simulated power with stated assumptions |
| R5 | Measure the fairness trade-off, including genuine beneficiaries without quotations | Paired trade-off and ratio; non-inferiority margin −0.10; at least 5 genuine-but-informal groups per category, with escalation and assisted-route outcomes |
| R6 | Keep independence rules; show recruitment is feasible before choosing the size | `prepare_independent_data_v5.py feasibility` on the registry (committed hours, plus a 20% buffer). The design is chosen afterwards |
| R7 | Keep design A; assess design B realistically; never reduce silently | §9 |
| R8 | Keep documenting the retrieval difference | §6 and every report disclaimer |
| R9 | Model availability and quota are not verified | Marked unverified in the pre-registration, the plan and the reports |
| R10 | Keep the login-test issue separate | `docs/known_issue_campaign_verification_test.md`; nothing changed |

**Criteria approval (owner, 2026-11-17).** Recorded in `preregistration.json` → `owner_approvals`, with a snapshot that `preseal-check` compares against before sealing.

| ID | Approved |
|---|---|
| A1 | Fraud recall: H1 lower 95% bound ≥ 0.70 (minimum); R1 research target ≥ 0.80 |
| A2 | Every zero-tolerance gate kept, including unsafe activation from collusive documents and cost-issuer-only fraud |
| A3 | K1: false-positive upper 95% bound ≤ 0.10 |
| A4 | K2: legitimate-approval lower bound ≥ 0.50, **as a preliminary evaluation floor only**. Never represented as sufficient for production readiness |
| A5 | Fairness non-inferiority margin of −10 points versus hybrid v2 |
| A6 | At least 5 genuine-but-informal groups per relevant category. All three categories are treated as relevant |
| A7 | Group-aware intervals, paired cluster comparisons and multiple-testing corrections retained |
| A8 | Model availability and quota recorded as unverified |
| A9 | No API calls or paid usage authorised |

**Known weakness: no commitment to soften it.**
- The frozen workflow cannot independently verify the requested amount. This is a known safety weakness.
- Gate G2 is not weakened, narrowed or redefined to accommodate it. If hybrid v3 fails G2, the report states that the candidate failed.
- The frozen candidate is never modified to make this evaluation pass. Any change is a new candidate (D10), with its own freeze, evaluated on test data it has not been evaluated on before.

**Scope of the verdict.**
- MEETS_MINIMUM_STANDARD is a preliminary standard for a development candidate under simulated confirmation. It is not evidence of production readiness.
- Every score report carries this statement.

## 3. Unseen data and independence

**Excluded material.** This material is never used, modified or relabelled as test data:
- the 750 benchmark cases;
- the 10 historical Gemini cases;
- the 8 date-aware templates and rendered cases;
- development sets v1–v3 (all variants);
- every long string literal in the test suite;
- the v4 and v5 example cases;
- the v5 engineering fixtures.

**How exclusion is enforced.**
- `independent_v5/exclusion_registry.json` lists 41 sources with SHA-256 hashes, covering 3,832 texts.
- If a dataset corpus is missing or changed, validation fails.
- Test files may change; their registered texts stay excluded by hash.

**Duplicate protection.** Every story and document is checked:
- against all excluded material;
- against the pilot set;
- against every other scenario group in the submission.

The checks:
- **Normalisation:** digits become `#`, so changing amounts, dates or IDs does not evade a match.
- **Exact matches** on texts of at least 8 words.
- **Near matches:** 3-word-shingle Jaccard of at least 0.5, or containment of at least 0.7.
- **Short-text reuse:** at least 90% containment for texts under 20 shingles.
- **v4's story token rule.**
- **Near-copies within a group:** story Jaccard of at least 0.8 is an error.

**People.** The participant registry (`independent_test_v5/participants_template.csv`) holds pseudonymous codes only; the coordinator keeps real identities outside the repository.
- **Who may participate.** Authors, labellers and adjudicators must sign `INDEPENDENCE_DECLARATION.md`, answer "no" to all four involvement questions, and hold one role only. The validator rejects anyone else.
- **Excluded by rule:** the developer and the AI assistant. Reserved IDs such as `DEVELOPER` and `CLAUDE` are rejected.
- **Labellers** must not have authored cases. **Adjudicators** must not be one of the case's labellers.
- **Coordinator.** May be the developer, but then only validates, seals and runs the sealed tools, and does not read cases before scoring.

**LLM-assisted cases** are marked by their authors, counted separately and reported as a subgroup.

**Recruitment feasibility before sizing (R6).**
- Participants are registered with `committed_hours`.
- `prepare_independent_data_v5.py feasibility` checks each design. It needs at least 3 eligible authors, 2 eligible labellers, an eligible adjudicator and a coordinator, whose committed hours cover the design's hours plus 20%.
- The owner chooses the design only after this check passes. The sample size is never reduced without the owner's approval.
- The checklist and per-person effort are in `docs/independent_v5_recruitment.md`.

**Participant access.**
- Participants never receive repository access. Each receives a role packet (`prepare_independent_data_v5.py packet`), built outside the repository from an allowlist, with a hash manifest.
- Labellers and the adjudicator also receive the blinded cases. The build fails if any field hidden from labellers is present.
- A packet never contains code, prompts, rule or keyword lists, earlier datasets or system outputs.

## 4. Case design

**Strata** come from the adjudicated labels:

| Stratum | Definition |
|---|---|
| L | Legitimate, complete |
| I | Legitimate, incomplete |
| F | Fraudulent |
| B | Borderline |

**Preferred design (D7):** per category (MEDICAL, EDUCATION, COMMUNITY), L 30, I 15, F 30 and B 15 groups. That is 270 groups and at most 540 cases.

**Quotas checked by the validator:**
- Every fraud mechanism makes up at least 12% of fraud groups in each category. The mechanisms are consistent fabrication, independent-record contradiction, suspicious payee, document contradiction, amount inflation and misrepresented need.
- At least 50% of fraud groups in each category are *intended* to be detectable from the documents (author field `intended_detectable_from_dossier`, hidden from labellers). This gives the primary endpoint about 45 groups. The analysis uses the labellers' adjudicated judgement.
- Within document contradiction, each form (structured, prose) is at least 40%.
- At least 30% of fraud cases are keyword-free, with at least one keyword-free group per mechanism. Keyword-free cases are checked against every lexicon.
- Incomplete subtypes per category: at least 3 groups each of no cost document, unacceptable cost document, and missing identity or need, and **at least 5 groups of genuine but informal** (R5).
- At least 20% of L cases have six or more production chunks.
- At least 15% of cases in each category are date-sensitive.

**Dates (D8).**
- `submitted_on` is each case's reference date, for the prompt and for every check.
- Authors declare `date_facts`, each with the text exactly as written, the ISO date and a role.
- `independent_v5/datecheck.py` is a parser that imports nothing from the system under test. It checks that each written date appears verbatim and reads as the declared date. It also checks that past roles (issue, completed event, death) are not after submission unless marked as an intentional anomaly. It warns about scheduled events in the past and expired documents in cases declared complete.
- Labellers independently record `date_check`.

**Case format:** `independent_test_v5/example_case.json` and `AUTHORING_GUIDE.md`. Each case includes the four-party external environment: beneficiary, payment destination, institution, and the cost issuer with the amount it states.

## 5. Labelling

1. **Blind copy.** The coordinator produces a copy without author intent, mechanism, gold titles or date facts: `prepare_independent_data_v5.py blind`.
2. **Independent sheets.** Two labellers each fill a sheet: truth, documentation and missing items, detectability, decisive titles, justified amount, acceptable end states, date check.
3. **Sheet checks.** `labels-check` verifies coverage, allowed values and labeller eligibility. APPROVED is acceptable only for legitimate, complete cases.
4. **Agreement.** `labels-agreement` reports Cohen's κ for truth, documentation and date check, and lists every disagreement.
5. **Adjudication.** A third person records a value and reason for each disagreement (`labels-adjudication-template`, then `labels-merge`). An unresolved truth or documentation disagreement makes the case `borderline`, marked unresolved. Every decision goes into the adjudication log.
6. **Sealing.** `labels-seal` hashes the adjudicated file before any run. The scorer refuses labels that differ from their seal, and labels never change after results exist.

## 6. Execution pipeline (per case, in a seeded random order)

1. **Frozen V3**, offline.
2. **Retrieval (D3).**
   - `app.services.rag.retrieve_evidence` is called **unchanged**. Documents are written as `.txt` uploads in a temporary directory. Rag sees no key, so production takes its own lexical fallback. Its HTTP helper is replaced by a guard that refuses and records any request.
   - The query and location use the production formats.
   - Production chunking (220 words, 40 overlap, at most 60 chunks), top 5.
   - **Difference from production:** production's primary path embeds the query and chunks with `gemini-embedding-001` (2 HTTP requests per campaign) and ranks by cosine similarity. Rankings can differ whenever a case has more than five chunks.
   - **Claim restriction:** results describe hybrid v3 with production's no-embedding fallback, not the exact production pipeline. Coverage (all chunks retrieved or not) is recorded per case.
3. **One Gemini call** through the frozen hybrid-v2 client and the budgeted transport. At most one retry for a transient failure.
4. **Scoring.** Hybrid v3, hybrid v2 and V3 alone all score the same answer (D4).
5. **Workflow.** Each decision starts a record in the frozen workflow, with the same rules for all systems.
6. **Simulated confirmation** from the sealed environment:
   - campaign-supplied contacts are offered first, and must never satisfy a check;
   - then independently sourced contacts are used.
7. **Simulated amount check (D5),** for activated campaigns only: the cost issuer's stated amount minus other payers, compared with the goal at 5% tolerance. This is a secondary analysis, not part of the frozen system.

Outputs contain case IDs, groups and system outputs. They contain no labels and no author-intent fields.

## 7. Measurements, statistical method and success criteria (D9, R1–R5)

Exact definitions are in `preregistration.json` → `metrics` and `success_criteria`; `independent_v5/scorer.py` implements them. The validation evidence is in `docs/independent_v5_statistical_methodology.md`.

**Conventions:**
- **Detection:** FLAG_FOR_REVIEW or REJECTED only.
- **Populations:** intent-to-treat is primary (a Gemini failure is VERIFICATION_ERROR); complete-case is secondary.
- **Primary interval:** Wilson on n_eff = n / DEFF, DEFF = 1 + (m̃ − 1) · ICC.
  - m̃ = Σ m_i² / n (Kish).
  - ICC by one-way ANOVA over scenario groups, floored at 0.10, capped at 1, and set to 1 when not estimable.
  - n, groups, m̃, ICC, DEFF and n_eff are reported for every rate.
- **Secondary intervals:** cluster bootstrap; group-level majority Wilson.
- **Paired test:** exact cluster sign-flip.
- **Zero events:** exact one-sided 95% upper bound 1 − 0.05^(1/n_eff).

**Measurements:**

| Area | Measurements |
|---|---|
| Fraud detection | Fraud recall (M1); recall on dossier-detectable fraud (M1a); fraud held before activation (M1b, simulated) |
| Errors and precision | False-positive rate (M2); fraud precision (M3), also re-weighted to 2%, 5% and 10% prevalence with conservative bounds |
| Approvals | Legitimate approval: complete (M4), all (M4b), activated (M4c, simulated) |
| Information requests and review | M5, M5L, M5I; M6, M6nf, and review basis |
| Unsafe provisional approvals | M7I, M7F, M7Fd, M7B |
| Unsafe activations | M8 types (a)–(e), with the decomposition of fraud activations |
| Stage funnel | S1–S4 (§8) |
| Independent-confirmation failures (simulated) | M9a–M9d |
| Undetectable fraud | N1, by mechanism |
| Fairness | F1 genuine-but-informal outcomes and escalation; F2 assisted-route resolvability; F3 outcomes by category and beneficiary type; F4 trade-off |
| API | Reliability (M10) and latency (M11) |

**What decides the result:**

| Layer | Content | Error control |
|---|---|---|
| Gates G1–G5 | No provisional approval of an incomplete case; **no unsafe activation of any type, including any fraud activation**; no Gemini-only rejection; provisional approval never treated as activation; no campaign-supplied confirmation accepted | Zero observed events; one-sided upper bounds reported |
| Primary endpoint H1 | Recall on dossier-detectable fraud, 95% lower bound ≥ **0.70** (minimum safety threshold) | One-sided α = 0.025 |
| Key secondary K1, K2 | FPR upper bound ≤ 0.10; legitimate-complete approval lower bound ≥ 0.50 | Part of the verdict |
| Verdict | MEETS_MINIMUM_STANDARD only if every gate passes and H1, K1 and K2 are MET | Intersection-union |
| Research target R1 | Dossier-detectable recall lower bound ≥ **0.80** | Fixed sequence after H1 |
| Comparisons with hybrid v2 | Fraudulent provisional approvals; legitimate-complete approvals; dossier-detectable recall; FPR | Holm over 4; claim only if Holm p < 0.05 and the bootstrap interval excludes 0 |
| Fairness non-inferiority | Legitimate-complete approval, v3 − v2: lower bound > −0.10 | Single pre-specified assessment |
| Descriptive benchmarks | Avoidable and appropriate information requests; non-fraud review; dossier-detectable fraud approved; borderline approved; genuine-but-informal escalation; API reliability and latency | No claim from any single item |

**Judgement rule.**
- **MET:** the bound clears the threshold.
- **INCONCLUSIVE:** the point estimate clears it, the bound does not.
- **NOT_MET:** the point estimate does not.

Thresholds never change after sealing.

**Statistical consequences** (methodology document §4 and §6):

*H1 (minimum).*
- With about 45 dossier-detectable fraud groups, H1 needs an observed recall of about 0.81–0.84.
- If true recall is 0.70, it passes about 2% of the time. If true recall is 0.85, it passes 64–86% of the time; if 0.90, 92–99.5%.

*R1 (research target).*
- Needs an observed recall of about 0.90–0.93.
- It is met with probability 0.33–0.59 if true recall is 0.90.

*The verdict.*
- It needs every component, so its power is roughly the product of theirs.
- For true recall 0.85, FPR 0.05 and approval 0.65, that is about 0.25–0.65 in design A. For recall 0.90, FPR 0.03 and approval 0.75, it is 0.82–0.99.

*Paired power* (cluster sign-flip, Holm worst case to unadjusted).
- **10-point one-directional difference:** 0.91–0.98 in A, 0.58–0.78 in B.
- **Mixed 10-point difference:** 0.55–0.74 in A, 0.29–0.52 in B.
- Small differences in recall or FPR are not detectable at this size. "No supported difference" is not evidence of equivalence.

**Undetectable fraud (R1).** Fraud the labellers judge not detectable from the documents has no recall threshold. It is reported by mechanism (detected, provisionally approved, held, activated), and its safety requirement is gate G2.

**Pre-registered expectation for G2.**
- The frozen workflow does not confirm amounts. Fraud that only the cost issuer reveals, and collusive fraud that no independent party reveals, can reach activation in the simulation and fail G2.
- The report attributes each such activation to one of these causes, and shows whether the simulated amount check would have caught it.

**Fairness (R5).**
- Trade-off between fraud prevented (detected, held, provisionally approved, finally approved, activated) and legitimate applicants delayed (approved, information request, flagged, error, activated), per system.
- Paired change from v2 to v3 in fraudulent provisional approvals and in legitimate-complete approvals.
- Legitimate approvals lost per fraudulent approval prevented, with an interval when estimable.
- Rates per 1,000 campaigns at 2%, 5% and 10% fraud prevalence.
- Genuine-but-informal outcomes and assisted-route resolvability.
- Approval rates by category and beneficiary type.
- The retrospective in-sample contrast (64 → 20 fraudulent, 231 → 162 legitimate approvals) is quoted only as context.

## 8. Provisional approval, independent confirmation, final approval and activation (R2)

| Stage | Definition | What it allows | Measured as |
|---|---|---|---|
| Provisional approval | Automated APPROVED → ELIGIBLE_PENDING_CONFIRMATION | Nothing public; authenticity UNCONFIRMED; no fundraising; no disbursement | S1 |
| Independent confirmation | Each required check (beneficiary, institution, payment destination) recorded as CONFIRMED through an independently sourced contact. A contradiction sends the campaign to FLAG_FOR_REVIEW; unreachable or inconclusive leaves it open; a campaign-supplied contact never counts | Nothing yet | S2 (checks confirmed per case) |
| Final approval | All three required checks independently CONFIRMED, none pending | The decision that the campaign may go live | S3 |
| Campaign activation | VERIFIED_ACTIVE, reached only by `record_confirmation` when the last check is confirmed. Never by automation or a reviewer (`IllegalTransition`) | Live; disbursement allowed | S4 |

- In the frozen workflow, final approval and activation happen in the same transition.
- The scorer still computes them separately. Activation without final approval is an unsafe activation (type b); final approval without activation is reported as a workflow defect.
- Separating disbursement into invoice-backed tranches (Appendix A) would be a new candidate (D10).

## 9. API usage, elapsed time and cost (estimates; nothing approved)

These figures come from `run_independent_test_v5.py plan`, which makes no calls.

**Assumptions:**
- Requests = N cases + ⌈0.10 N⌉ retries + 8 pilot requests. There are no embedding requests.
- Free tier: about 20 requests a day were observed for this model.
- Prompt size: the engineering fixtures average 3,667 characters; the bound for 5 full chunks and a long story is 23,664 characters. Tokens are estimated at about 4 characters each.
- Free tier: about 20 requests a day were observed once for this model. **This quota, and the model's current availability, are not verified.**
- Interval half-widths assume recall 0.60, FPR 0.05 and legitimate approval 0.70.
- Paired power is simulated, with the assumptions in the methodology document §3. It replaces the earlier formula figures, which ignored clustering and multiplicity.

| Design | Groups | Cases | Max requests | Free-tier days (min, unverified quota) | Verdict probability* | Paired power, 10-pt one-dir. (Holm worst – unadjusted) |
|---|---|---|---|---|---|---|
| A: preferred, 270 groups × ~2 | 270 | ≤ 540 | 602 | 31 | 0.25–0.65 / 0.82–0.99 | 0.91–0.98 |
| B: 270 groups × 1 | 270 | 270 | 305 | 16 | 0.25 / 0.82 | 0.58–0.78 |
| C: reduced, 150 groups × 1 | 150 | 150 | 173 | 9 | 0.04 / 0.35 | 0.08–0.29 |
| D: minimal, 90 groups × 1 | 90 | 90 | 107 | 6 | 0.01 / 0.11 | 0.02–0.09 |

\* Probability that a system with true recall 0.85, FPR 0.05 and approval 0.65 (first figure), or 0.90 / 0.03 / 0.75 (second), meets the minimum-standard verdict.

**Realistic assessment of design B (R7).** Design A remains preferred. B needs about 275 base hours (330 with buffer) instead of about 504 (605 with buffer).

*What B keeps:*
- all 270 scenario groups and every quota (mechanisms, subtypes, dates, keyword-free, detectability);
- the same verdict probability as A when correlation within groups is strong, because A's extra cases then add little information.

*What B loses:*
- **Robustness to re-presentation.** There is no second presentation of the same situation, so this cannot be studied.
- **Power for small paired differences:** 0.58–0.78 for a 10-point one-directional difference, 0.29–0.52 if mixed.
- **Zero-event bounds** become group-based only: 3.3% among fraud, against as low as 1.7% in A.
- **Genuine-but-informal cases:** 15 instead of about 30, so the escalation bound with zero events is 18%.

*Conclusion.* B is a credible fallback for the verdict-level questions. It is weaker for comparing hybrid v3 with hybrid v2 on small differences.

*C and D* would only be pilot-scale studies, unable to support a safety verdict (verdict probability 0.01–0.35). They are offered only with your explicit approval.

**Tokens (design A).**
- Input: about 0.55 million tokens typical, at most about 3.6 million.
- Visible output: at most 2,048 × 602 ≈ 1.23 million tokens.
- "Thinking" tokens are not capped by the output setting and are unknown until measured; `usageMetadata` is logged for every request.

**Cost.**
- **Free tier:** no API charge, but at least 31 days for design A. Free-tier terms may allow the provider to use prompts to improve its products, so only synthetic cases may be sent.
- **Paid usage is not approved.** For reference, the published standard price from 1 January 2027 is $1.50 per million input tokens and $7.50 per million output tokens, with thinking counted as output; it is $0.75 / $3.75 until 31 December 2026.
- At the 2027 price, design A would cost about $1–5 for input plus at most $9.25 for visible output, plus about $4.50 for every 1,000 thinking tokens per request.
- Design B is about half that.

**Human effort (assumption-based).** This is the dominant cost.

| Design | Authoring | Labelling (2 labellers) | Adjudication | Coordination |
|---|---|---|---|---|
| A | ~315 h | ~144 h | ~18 h | ~27 h |
| B | ~180 h | ~72 h | ~9 h | ~14 h |

## 10. Stopping rules (D11, approved as proposed)

**Stop permanently:**
- the authorised call cap is reached;
- a configuration error: authentication, permission, model not found, bad request, or no key;
- a freeze, seal or kit check fails at start or resume;
- after at least 100 requests, the cumulative transient-failure rate exceeds 25%;
- the retry allowance is used up;
- 45 calendar days have passed.

**Pause, then resume with an identical configuration:**
- **Quota exhausted:** until 08:00 UTC.
- **Three consecutive transient failures, or more than 20% transient failures in the last 25 requests:** 60 minutes. After the third such pause in one UTC day, wait until the next day.

**Retries.** At most one retry per case, only after a transient failure. Invalid outputs are final for that case.

**Never stop on results.** Interim status shows only:
- requests used;
- failure categories;
- cases completed;
- the pause or stop reason.

The runner never parses labels; it only compares the label file's hash with its seal. Safety-gate violations are results to report, not stopping triggers.

## 11. Tooling and order of work

| Purpose | Command |
|---|---|
| Data preparation | `prepare_independent_data_v5.py`: fixtures, exclusion registry, participants, feasibility, validate, validate-pilot, blind, packet, labels-check, labels-agreement, labels-adjudication-template, labels-merge, labels-seal |
| Runner | `run_independent_test_v5.py`: plan, integrity, dry-run (ENG- fixtures or pilot only), status, validate-statistics, preseal-check, seal-kit, verify-kit, execute (live; refuses without every precondition) |
| Scorer | `score_independent_test_v5.py score`. Standard library only; never imports `app`; writes once, outside `app/` |

**Tests.** `tests/test_independent_v5.py` exercises everything offline on the ENG- engineering fixtures, using a scripted fake Gemini and a guard that fails any network attempt.

**Order of work:**
1. Register candidate participants with committed hours, and run `feasibility` (R6).
2. The owner chooses the design (A preferred) and authorises status APPROVED.
3. Run `preseal-check --registry R --out REPORT`, the final offline check:
   - the criteria match the owner's approval;
   - the statistics meet their acceptance bounds and reproduce exactly;
   - the tooling tests pass;
   - the freezes and the `app/` tree are intact;
   - the exclusion registry is intact;
   - the packets are clean;
   - no independent case exists in the repository;
   - nothing blocks.

   Then run `seal-kit --preseal-report REPORT`, which refuses unless the report passes for exactly the current kit files.
4. Authors (who receive only the author packet) write the pilot cases, then the test cases. If the pilot shows that authoring takes materially longer than assumed, the effort estimate and feasibility check are re-run first. The coordinator validates the cases under the full profile and seals them.
5. Blind labelling (labeller packets), then agreement, then adjudication (adjudicator packet), then sealing the labels.
6. The owner writes the API authorisation file for the pilot (at most 8 requests). Run the pilot, which is never scored, and review the pipeline only.
7. A separate authorisation for the main run. Execute; pauses and resumes follow §10.
8. Score once, then write the report.

## 12. Data protection

- Synthetic cases only. The runner refuses non-synthetic cases until a separate data-processing approval exists.
- Pseudonymous participant codes.
- Request logs record no prompt content, no response text and no key.

## 13. Remaining requirements before sealing

See `docs/independent_v5_readiness.md`, section G. `run_independent_test_v5.py preseal-check` lists the items that still block sealing.

---

## Appendix A: independently confirming the requested amount (proposed procedure; simulated only, D5)

**Purpose.** Establish, through a channel the campaigner does not control, how much money the need actually requires. Compare that figure with the goal before any money moves.

**Steps.**

1. **Identify the cost issuer:** the hospital billing desk, the institution's accounts office, or the supplier or contractor.
2. **Source the contact independently.** Use:
   - official directories or websites;
   - state health-department lists or the NABH directory;
   - UDISE+ or AISHE for schools and colleges;
   - the GST portal for suppliers;
   - NGO Darpan or the registrar for organisations.

   Contacts printed in the uploads are recorded but never sufficient.
3. **Ask blind.** Give the identifier and the reference number, and ask the issuer to state:
   - the estimated or outstanding amount;
   - any insurance, PMJAY, scholarship, waiver or advance;
   - the account it accepts payment into.

   Never read out the campaign's figure first.
4. **Compare.**
   - **Within tolerance:** the goal is at most (stated amount − other payers) × 1.05. Record CONFIRMED.
   - **Above that:** record CONTRADICTED. The campaign goes to review, where it can be capped at the confirmed amount with the campaigner's consent.
   - **Cannot disclose:** have the issuer email the estimate directly, or obtain the beneficiary's signed consent.
   - **Unreachable:** the check stays open.
5. **Bind the money to the issuer.** Prefer direct payment to the issuer's verified account.
6. **Disburse in tranches.** For large goals (for example above ₹2 lakh) or long treatments, release money in tranches against invoices. Re-confirm when a confirmation is more than 30 days old.
7. **Community and organisation campaigns.** Confirm that the supplier exists (active GSTIN) and confirm its quotation. Cover the items making up at least 80% of the goal.
8. **Surplus and privacy.** State surplus handling in advance. Collect disclosure consent at creation and share the minimum data needed.

**In this evaluation** the procedure is simulated from the `COST_ISSUER` record and reported separately (M9d). It is never described as real-world verification. Making it a recorded workflow check requires a new candidate version (D10).

## Appendix B: fair review for genuine beneficiaries without formal cost quotations (proposed procedure)

**Principles.**
- A missing formal quotation leads to NEEDS_MORE_INFORMATION, never to rejection.
- The safety bar for activation does not change. What changes is who does the work to produce evidence, and which evidence is accepted.

**Steps.**

1. **Triage.**
   - Within 1 working day.
   - Within 24 hours when the documents show treatment within 14 days, or a reviewer judges the case urgent.
2. **A specific request** in plain language, in the campaigner's language, listing acceptable alternatives:

   | Category | Alternative evidence of cost |
   |---|---|
   | Medical | Government hospital's list of items to buy, with pharmacy or supplier quotes; the treating doctor's note naming the procedure, plus a billing-desk confirmation obtained by the platform; an insurance or PMJAY pre-authorisation showing covered and uncovered amounts; recent receipts for ongoing treatment establishing the running cost |
   | Education | Official fee structure from the website or prospectus; last term's receipt plus the current circular; a scholarship or waiver letter showing the balance; hostel or mess bills |
   | Community | Two supplier quotations; the government schedule of rates for construction items; invoices from a comparable earlier project |

3. **Assisted route.** A trained caseworker or a partner NGO obtains the amount independently from the institution, using the Appendix A procedure. The recorded, independently sourced figure substitutes for the quotation.
4. **Partial and direct options** (a policy change, needing a new version):
   - activation capped at the independently confirmed amount;
   - or direct payment to the institution against invoices.
5. **Reviewer rules.**
   - Reviewers cannot reject solely because a formal quotation is missing.
   - Any rejection needs two reviewers.
   - Reviewers see findings labelled by basis, and must not treat an UNVERIFIED_MODEL_SUSPICION as evidence.
   - Reasons come from a fixed list.
   - Appeals go to a different reviewer and are decided within 5 working days.
6. **Time limits.**
   - A decision within 3 working days of receiving evidence.
   - A request never expires automatically. After 14 days without a reply, the campaigner gets a reminder and a phone call.
7. **Fairness monitoring.** Each month, compare information-request rates, time to activation, abandonment and legitimate approval rates across:
   - category;
   - government and private hospitals;
   - language;
   - state;
   - rural and urban beneficiaries;
   - beneficiary type.

   A ratio below 0.8 between groups triggers a policy review (a screening heuristic).
8. **Data minimisation and consent** throughout.

**In this evaluation** the incomplete sub-type "genuine but informal" measures:
- how often such cases receive an information request rather than a flag (M5I, by subtype);
- how many could be resolved through the assisted route, i.e. where `COST_ISSUER` would confirm an amount.
