# Independent evaluation protocol v5: hybrid v3

**Status (2026-11-17)**

| Item | State |
|---|---|
| Tooling | Built and tested offline |
| Protocol, pre-registration and kit | Not sealed |
| Independent cases | None exist yet |
| Independent participants | **Not yet confirmed** |
| API calls | 0 made. 0 approved for this evaluation |

- The owner's decisions D1–D11 are recorded in §2.
- The machine-readable pre-registration is `independent_test_v5/preregistration.json`, status `PROPOSED`. It holds every definition, threshold and parameter used by the tools.
- Nothing runs live until the owner approves the open items in §13 and gives a separate written API authorisation.
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

**Model availability (D1), checked without an API call.**
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
| D4 | Compare frozen hybrid v2 and hybrid v3 on the same Gemini responses; paired, case level | §7 M12. One answer per case is scored by both, plus V3 alone. Exact McNemar test with cluster-bootstrap intervals and Holm adjustment |
| D5 | Amount confirmation stays a pre-registered simulation, measured separately, never claimed as real | §6 step 7 and M9d. Every output is labelled "SIMULATED … not real-world verification" |
| D6 | Independent authorship and blind labelling approved; confirm participants exist; exclude anyone involved | §3. Participant registry, signed declarations and automated eligibility checks. **Availability not yet confirmed** |
| D7 | Keep the 270-group design as preferred; do not execute; give usage, time and cost; propose an explicitly weaker alternative if needed | §9. Four designs with intervals and power |
| D8 | Use each scenario's submission date; validate date-sensitive scenarios independently | §4. `submitted_on` is "today". Authors declare `date_facts`; an independent parser checks them; labellers record `date_check` |
| D9 | Pre-register definitions and success criteria with intervals; report the fraud-versus-delay trade-off; provisional ≠ activation | §7. Numeric thresholds are **proposed** and need approval before sealing |
| D10 | Any post-freeze change creates a separately versioned candidate | Freeze rule. Appendix procedures A and B are not in this candidate |
| D11 | Operational stopping rules; never stop on accuracy; no label inspection during execution | §10. The runner never parses labels (hash check only); interim status shows counters only |

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
- Within document contradiction, each form (structured, prose) is at least 40%.
- At least 30% of fraud cases are keyword-free, with at least one keyword-free group per mechanism. Keyword-free cases are checked against every lexicon.
- Each incomplete subtype has at least 3 groups per category. The subtypes are no cost document, unacceptable cost document, missing identity or need, and genuine but informal.
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

## 7. Measurements and success criteria (D9)

Exact definitions are in `preregistration.json` → `metrics`; `independent_v5/scorer.py` implements them.

**Conventions:**
- **Detection:** FLAG_FOR_REVIEW or REJECTED. NEEDS_MORE_INFORMATION, APPROVED and VERIFICATION_ERROR are never detections.
- **Provisional approval** (APPROVED → ELIGIBLE_PENDING_CONFIRMATION) is never counted as activation; activation is only VERIFIED_ACTIVE reached in the simulation.
- **Primary population:** intent-to-treat (all cases; a Gemini failure is VERIFICATION_ERROR). Secondary: complete-case.
- **Intervals:**
  - **Primary:** Wilson on the design-effect-adjusted sample size, n / (1 + (m − 1)·ICC). ICC comes from a one-way ANOVA over scenario groups, floored at 0; it is set to 1 when it cannot be estimated, which is conservative for zero-event metrics.
  - **Secondary:** cluster bootstrap over groups (5,000 replications, fixed seed), plus group-level majority Wilson.
  - **Precision:** cluster bootstrap, because its denominator is itself an outcome.

**Measurements:**

| Area | Measurements |
|---|---|
| Fraud detection | Fraud recall (M1); recall on dossier-detectable fraud (M1a); fraud held before activation (M1b, simulated) |
| Errors | False-positive rate (M2) |
| Precision | Fraud precision (M3); sensitivity version counting borderline as negative (M3s) |
| Approvals | Legitimate approval rate: L (M4), L + I (M4b), activation (M4c, simulated) |
| Information requests | Overall (M5); avoidable, on L (M5L); appropriate, on I (M5I) |
| Manual review | Overall (M6), by review basis; non-fraud (M6nf) |
| Unsafe provisional approvals | Incomplete (M7I); fraud (M7F); dossier-detectable fraud (M7Fd); borderline (M7B) |
| Unsafe activations | Fraud (M8a, simulated); with an unconfirmed check (M8b); of incomplete cases (M8c); without a confirmation record (M8d); via a campaign-supplied contact (M8e) |
| Independent-confirmation failures (simulated) | Fraud passing confirmation (M9a); legitimate cases blocked at confirmation (M9b); campaign-supplied confirmations accepted (M9c); amount check (M9d) |
| API | First-attempt success, valid-answer coverage, invalid-output rate, outcome categories, retries, quota pauses, `modelVersion` values and token counts (M10); HTTP-only latency median, p90, p95 and max with bootstrap intervals, plus timeouts (M11) |
| Comparisons and trade-off | Paired case-level comparisons (M12); trade-off (M13) |

**Safety gates for hybrid v3.** A gate passes only with zero observed events; the 95% upper bound is also reported.

| Gate | Requirement |
|---|---|
| G1 | No provisional approval of an incomplete case |
| G2 | No unsafe activation of types b–e |
| G3 | No rejection based on Gemini alone |
| G4 | Provisional approval never treated as activation |
| G5 | No campaign-supplied confirmation accepted |

**Proposed performance criteria (need approval).** These apply to hybrid v3, intent-to-treat, primary interval.
- **MET** means the 95% bound clears the threshold.
- **INCONCLUSIVE** means the point estimate clears it but the bound does not.
- **NOT_MET** means the point estimate does not.

| Criterion | Metric | Threshold |
|---|---|---|
| C1 | Recall on dossier-detectable fraud | lower bound ≥ 0.50 |
| C2 | Fraud precision | lower bound ≥ 0.70 |
| C3 | False-positive rate | upper bound ≤ 0.10 |
| C4 | Legitimate (complete) approval rate | lower bound ≥ 0.50 |
| C5 | Avoidable information requests (L) | upper bound ≤ 0.40 |
| C5b | Appropriate information requests (I) | lower bound ≥ 0.70 |
| C6 | Non-fraud manual-review rate | upper bound ≤ 0.20 |
| C7 | Dossier-detectable fraud provisionally approved | upper bound ≤ 0.10 |
| C7b | Borderline provisionally approved | upper bound ≤ 0.15 |
| C8 | Fraud activations (simulated) | upper bound ≤ 0.10 |
| C10 | First-attempt API success | lower bound ≥ 0.85 |
| C10b | Valid-answer coverage | lower bound ≥ 0.90 |
| C10c | Invalid-output rate | upper bound ≤ 0.05 |
| C11 | Latency p95 | ≤ 60 s (point estimate) |

**How the thresholds were chosen.**
- They are policy judgements set before any independent data exists. They are not calibrated to an external benchmark.
- Recall is judged on dossier-detectable fraud, because fraud invisible in the documents is, by design, left to external confirmation; it is covered by C8 and M1b.
- There is no composite pass mark.

**Paired claims (D4).** Hybrid v3 is reported as better or worse than hybrid v2 on M1, M2, M4 or M7 only if both hold:
- the Holm-adjusted exact McNemar p is below 0.05;
- the cluster-bootstrap 95% interval of the case-level difference excludes 0.

**Trade-off (M13).** For each system the report shows two sides:
- **Fraud:** detected, held before activation, provisionally approved, activated.
- **Legitimate applicants:** provisionally approved, delayed by an information request, flagged, errored, activated.

It also reports:
- the extra legitimate delays per extra fraud case detected, against hybrid v2;
- rates per 1,000 campaigns re-weighted to fraud prevalence of 2%, 5% and 10% (the test mix of about one-third fraud is not real-world prevalence).

## 8. Provisional approval, final approval and activation

| Stage | State | How it is reached | What it allows |
|---|---|---|---|
| Automated decision | APPROVED → ELIGIBLE_PENDING_CONFIRMATION | Hybrid v3 finds no contradiction, no open item, supported financial evidence and a clean Gemini answer | Nothing public. Authenticity UNCONFIRMED; no fundraising; no disbursement. This is **provisional approval** |
| Confirmation | stays ELIGIBLE_PENDING_CONFIRMATION | Each check is recorded. A contradiction sends the campaign to FLAG_FOR_REVIEW; an unreachable or inconclusive contact leaves it open; a campaign-supplied contact never satisfies a check | — |
| Final approval and activation | VERIFIED_ACTIVE | Only `record_confirmation`, when the last required check is CONFIRMED through an independent source. Automation and reviewers cannot set it (`IllegalTransition`) | Live, with disbursement allowed |
| Review | FLAG_FOR_REVIEW | A contradiction, a model warning, or a suspension | A reviewer can return the campaign to pending, which resets every check; a reviewer can never activate it |

In the frozen workflow, final approval and activation are a single event. Separating activation from tranche-wise disbursement (Appendix A) would be a new candidate (D10).

## 9. API usage, elapsed time and cost (estimates; nothing approved)

These figures come from `run_independent_test_v5.py plan`, which makes no calls.

**Assumptions:**
- Requests = N cases + ⌈0.10 N⌉ retries + 8 pilot requests. There are no embedding requests.
- Free tier: about 20 requests a day were observed for this model.
- Prompt size: the engineering fixtures average 3,667 characters; the bound for 5 full chunks and a long story is 23,664 characters. Tokens are estimated at about 4 characters each.
- Interval half-widths assume recall 0.60, FPR 0.05 and legitimate approval 0.70.
- Power assumes a 10-point paired difference with 20% discordance (approximate).

| Design | Groups | Cases | Max requests | Free-tier days (min) | Recall ± | FPR ± | Legit. approval ± | Zero-event upper bound (I) | Paired power, fraud / legit |
|---|---|---|---|---|---|---|---|---|---|
| A: preferred, 270 groups × ~2 | 270 | ≤ 540 | 602 | 31 | 0.07–0.10 | 0.03–0.04 | 0.07–0.09 | 4.1–7.9% | 0.86 / 0.96 |
| B: 270 groups × 1 | 270 | 270 | 305 | 16 | 0.10 | 0.04 | 0.09 | 7.9% | 0.57 / 0.74 |
| C: reduced, 150 groups × 1 | 150 | 150 | 173 | 9 | 0.14 | 0.05 | 0.13 | 11.4% | 0.32 / 0.49 |
| D: minimal, 90 groups × 1 | 90 | 90 | 107 | 6 | 0.17 | 0.07 | 0.16 | 20.4% | 0.23 / 0.32 |

**Precision versus power.**
- Design B keeps nearly all of A's group-level precision for half the calls and half the authoring, because cases within a group are correlated.
- B does lose power for paired case-level comparisons (0.86 → 0.57 for fraud).
- C and D explicitly reduce both precision and power. They are offered only if staffing is insufficient, and never as a silent reduction.

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
| Data preparation | `prepare_independent_data_v5.py`: fixtures, exclusion registry, participants, validate, validate-pilot, blind, labels-check, labels-agreement, labels-adjudication-template, labels-merge, labels-seal |
| Runner | `run_independent_test_v5.py`: plan, integrity, dry-run (ENG- fixtures or pilot only), status, seal-kit, verify-kit, execute (live; refuses without every precondition) |
| Scorer | `score_independent_test_v5.py score`. Standard library only; never imports `app`; writes once, outside `app/` |

**Tests.** `tests/test_independent_v5.py` exercises everything offline on the ENG- engineering fixtures, using a scripted fake Gemini and a guard that fails any network attempt.

**Order of work:**
1. The owner approves the §13 items. The pre-registration status is set to APPROVED, and `seal-kit` is run.
2. Confirm and register participants (D6).
3. Authors write the pilot and test cases. The coordinator validates them under the full profile and seals them.
4. Blind labelling, then agreement, then adjudication, then sealing the labels.
5. The owner writes the API authorisation file for the pilot (at most 8 requests). Run the pilot, which is never scored, and review the pipeline only.
6. A separate authorisation for the main run. Execute; pauses and resumes follow §10.
7. Score once, then write the report.

## 12. Data protection

- Synthetic cases only. The runner refuses non-synthetic cases until a separate data-processing approval exists.
- Pseudonymous participant codes.
- Request logs record no prompt content, no response text and no key.

## 13. Items still requiring the owner's approval

See `docs/independent_v5_readiness.md`, section G.

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
