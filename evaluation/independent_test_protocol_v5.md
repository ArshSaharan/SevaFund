# Independent evaluation protocol v5: hybrid v3 (DRAFT, not sealed, not executed)

**Status.**

- **Draft, awaiting approval.** No test cases exist yet, no labels exist, nothing has been run, and no API calls have been made.
- **Sealing.** Once the decisions in §12 are approved, the protocol is finalised, hashed and sealed. The v5 tooling (§10, step 2) is then built and frozen. Only after that are authors briefed.
- **Relation to v4.** This protocol supersedes `independent_test_protocol_v4.md` for hybrid v3. v4 was written for hybrid v2 and never executed. v5 keeps every v4 independence rule and adds:
  - an incomplete-documentation stratum;
  - ground truth for the requested amount;
  - separate measurement of provisional approval and activation;
  - API reliability measurement;
  - a call budget and stopping rules.

## 1. System under test

| Item | Value |
|---|---|
| Candidate | hybrid v3, policy `hybrid-v3-dev-1`, settings digest `a01273d9e3c89b0e` |
| Freeze manifest | `evaluation/hybrid_v3_freeze.json` (verify with `python evaluation/freeze_hybrid_v3.py verify`) |
| Behavioural fingerprint | `2d117adb47d30d5c0eaef571845f2c784d9a2f1c623b0074c3147e52b5e840f8` |
| Code commits | `9152090` (package, tests, offline run), `d0479ab` (report) |
| Frozen dependencies | frozen V3 (`1c7e739`), hybrid v2 (`b9f7514`); both freezes verify |
| Gemini prompt | frozen date-aware prompt of hybrid v2 (`development_gemini_verification/prompt.py`), temperature 0.1, JSON schema output, 2,048 max output tokens |
| Model | not fixed by the code; chosen in decision D1 and recorded in the run manifest |

Hybrid v3 makes no model call of its own. It consumes the Gemini answer produced by the frozen hybrid-v2 client. One Gemini answer per case can therefore be scored by hybrid v3, hybrid v2 and frozen V3 alone, paired, with no extra API calls.

**Comparators (paired, same cases, same Gemini answer):**
- hybrid v2 (`hybrid-v2-dev-1`);
- frozen V3 alone plus the approval workflow (deterministic, no API).

The production-prompt system is excluded by default because it would need a second call per case (decision D4).

**Freeze rule.** If any recorded file changes, the result no longer describes this candidate. Defects found during the test are reported, not fixed; a fix becomes a new version that needs a new freeze and a new, unseen test set.

## 2. What counts as unseen data

**Never used as independent test data, and never reused, modified or relabelled for that purpose:**

| Excluded material | Reason |
|---|---|
| The 750 benchmark cases (`final_test_scenarios_v3.jsonl` 300, `fundraising_scenarios.jsonl` 200, `independent_test_150.jsonl`, `independent_benchmark_100.jsonl`) | Written by the developer from templates and inspected during development; the hybrid v3 financial classifier was adjusted after looking at them |
| The 10 historical Gemini cases (`gemini_eval_v1/cases.jsonl`) | Hybrid v2's policy was designed on their outputs |
| The 8 date-aware cases (`date_aware_dev_eval/scenarios.json`) | Hybrid v3 was designed to fix their failures |
| Development sets v1–v3 (all variants) | Development data |
| Test fixtures in `tests/test_hybrid_v2.py` and `tests/test_hybrid_v3.py` | Written to exercise the rules |

**Novelty check.** The v5 validator rejects any case whose story is a near-duplicate of anything in this list (token Jaccard ≥ 0.8), or whose document text is (Jaccard ≥ 0.8 against any prior document). This extends v4's check, which did not cover the date-aware cases, the contradiction-only and initial V3 sets, or the fixtures.

**People.**
- Authors and labellers must never have seen:
  - the verifier code or its lexicons;
  - this protocol's description of the rules (§1, §7, appendices);
  - any excluded corpus.
- They receive only:
  - `independent_test_v5/AUTHORING_GUIDE.md` (authors) or the labelling instructions (labellers);
  - `independent_test_v5/REQUIRED_EVIDENCE_POLICY.md`, the platform's published documentation policy (both groups);
  - the example case.
- Neither the developer nor Claude, which helped build the system, may author or label cases.
- The coordinator should ideally not be the developer. If they must be, they may only:
  - validate and seal submissions;
  - run the sealed runner;

  and must not read any case before every metric has been written (§10).

**LLM-assisted cases.** A case drafted with any language model is marked `llm_assisted: true`. LLM-assisted cases are reported as a separate stratum and are never pooled into the primary independent result (decision D6).

## 3. Case design

**Unit of analysis:** the scenario group, holding 1–3 cases written by one author that differ meaningfully (amounts, documents, people, wording).

**Strata.** Ground truth has two axes, assigned by the labellers (§4):

- **truth:** `legitimate`, `fraudulent` or `borderline`;
- **documentation:** `complete` or `incomplete`, judged against the published Required Evidence Policy, not against the code.

| Stratum | Definition | Groups per category | Groups in total |
|---|---|---|---|
| L: legitimate, complete | Genuine need; every required item present | 30 | 90 |
| I: incomplete | Genuine need, at least one required item missing or not acceptable | 15 | 45 |
| F: fraudulent | Material misrepresentation (complete or incomplete) | 30 | 90 |
| B: borderline | A careful reviewer genuinely needs more information to decide | 15 | 45 |
| Total | 3 categories: MEDICAL, EDUCATION, COMMUNITY | 90 | 270 groups (≤ 540 cases) |

**Precision at this size** (Wilson 95%, group level):

| Quantity | Example result | 95% interval |
|---|---|---|
| Fraud recall | 54/90 groups | 49.7–69.5% |
| False-positive rate | 7/135 legitimate groups | 2.5–10.3% |
| Zero unsafe approvals | 0/45 incomplete groups | upper bound 7.9% |
| Zero unsafe approvals | 0/90 incomplete cases | upper bound 4.1% (case level) |

A reduced design (15/10/15/10 groups per category, 150 in total) widens the recall interval to about ±14 points (decision D7).

**Fraud mechanisms.** Each must make up at least 12% of fraud groups in every category:

1. `consistent_fabrication`: fabricated institution, beneficiary or need, with every document agreeing with every other. Only the external environment reveals it.
2. `independent_record_contradiction`: the documents agree, but an independent record contradicts them (already paid, seat withdrawn, registration lapsed).
3. `suspicious_payee`: the payout goes to someone who should not receive it.
4. `document_contradiction`: identity, date, treatment or amount conflicts between documents or between story and documents. Each case records a `form` attribute:
   - `structured`: in fields such as dates, IDs or amounts;
   - `prose`: in free text, such as "died at home" against "died in the ICU".

   Each form makes up at least 40% of this mechanism. This tests both the deterministic checks and the Gemini-dependent list.
5. `amount_inflation`: genuine need, but the goal overstates it. Examples:
   - inflated or doctored quote;
   - cost already covered by insurance, PMJAY or a scholarship;
   - the same bill used twice.
6. `misrepresented_need`: the documents show the claimed treatment or purpose is not needed or not happening, for example "no surgery indicated" or "not enrolled".

**Cross-cutting requirements:**
- At least 30% of fraud cases, with at least one group in every mechanism, are `keyword_free`: they contain none of the red-flag or semantic-lexicon terms. A script checks this; authors never see the word list.
- In v4, `keyword_free` was a mechanism of its own. v5 makes it a style constraint across all mechanisms, so it cannot be satisfied only by one easy type.

**Required content in the other strata:**

- **L (legitimate, complete):**
  - high but justified costs;
  - scheduled future events (surgery, exam and admission dates);
  - documents with explicit validity periods;
  - partial insurance or scholarship cover with a correctly stated balance;
  - regional-language headings;
  - OCR noise;
  - campaigns written by a third party;
  - at least 20% of cases with more than five document chunks, so retrieval coverage is exercised.
- **I (incomplete):** at least 3 groups per category of each sub-type:
  - (a) no cost document at all;
  - (b) a cost document that is unacceptable (expired, issuer not identifiable, below the goal);
  - (c) missing proof of identity, enrolment or diagnosis;
  - (d) **genuine but informal**: the family cannot obtain a formal quotation, for example from a government hospital or for informal tutoring. These cases test the fair-review procedure (Appendix B).
- **B (borderline):** the adjudicated acceptable outcomes are NEEDS_MORE_INFORMATION or FLAG_FOR_REVIEW, never approval.

**Case format.** Same as v4, plus:
- `submitted_on`, required;
- `llm_assisted`;
- `mechanism` and `form`;
- an `incomplete_subtype`;
- a fourth external party, `COST_ISSUER`.

`COST_ISSUER` records what the issuer of the cost document would state when asked independently through its own official channel:

- `independent_response`;
- `amount_stated_inr`: a number, or null if the issuer cannot or will not disclose it;
- `other_payers_inr`: insurance, scheme, scholarship or advance already paid;
- `note`;
- optionally `campaign_supplied_contact`.

See `independent_test_v5/example_case.json`.

## 4. Labelling

**Who.**
- Two labellers per case, working independently and blind to every system's output, assign the label sheet fields (`independent_test_v5/labeling_sheet_template.csv`).
- A third person adjudicates disagreements.

**Label sheet fields:**
- truth label;
- documentation completeness, with the missing items named from the policy;
- whether the fraud is detectable from the dossier or only externally;
- the decisive evidence titles;
- the justified amount: what the documents support, in INR, or blank;
- the set of acceptable end states.

**Agreement and sealing.**
- Cohen's κ is reported before adjudication, separately for truth and for completeness.
- Labels are hashed and sealed before any system runs, and never changed afterwards.
- A case with κ-disagreement that the adjudicator cannot resolve is labelled `borderline`. Such cases are listed in the report.

**Acceptable outcomes by stratum:**

| Stratum | Counted as correct | Counted as error | Reported separately |
|---|---|---|---|
| L | APPROVED | FLAG/REJECTED (false positive) | NEEDS_MORE_INFORMATION (avoidable request) |
| I | NEEDS_MORE_INFORMATION | APPROVED (unsafe provisional approval); FLAG/REJECTED (false positive) | — |
| F | FLAG/REJECTED (detection) | APPROVED (unsafe provisional approval) | NEEDS_MORE_INFORMATION (held, not detected) |
| B | NEEDS_MORE_INFORMATION or FLAG | APPROVED (unsafe provisional approval) | — |
| Any | — | — | VERIFICATION_ERROR (system unavailable; never an approval) |

## 5. Execution pipeline (per case, in a pre-registered random order)

1. **Frozen V3** (offline).
2. **Retrieval:** frozen lexical top-5 by default, with no embedding calls (decision D3). Chunk coverage is recorded for every case.
3. **One Gemini call** through the frozen hybrid-v2 client, using a budgeted transport:
   - each call is one HTTP request, with no hidden retries;
   - every request counts against the cap;
   - the log records stage, model, `modelVersion` when the provider returns it, outcome and HTTP-only latency;
   - the log never records content or the key.
4. **Scoring:** hybrid v3, hybrid v2 and V3 alone, all scored on the same answer.
5. **Workflow start.** `start_record` creates the initial state: an APPROVED decision becomes ELIGIBLE_PENDING_CONFIRMATION, with three required checks.
6. **Confirmation simulation** from the sealed external environment:
   - the simulated verifier contacts only independently sourced parties;
   - a second pass offers the campaign-supplied contacts, to test that they are never accepted;
   - the end state and the number of contacts are recorded;
   - sensitivity runs use `simulate_external_confirmation.py` with a pre-registered grid of verifier error and compromised-directory rates.
7. **Amount-confirmation analysis** (secondary, simulated; Appendix A):
   - compares `COST_ISSUER.amount_stated_inr − other_payers_inr` with the goal, at 5% tolerance;
   - is not part of the frozen system;
   - is labelled as an add-on.

**Reference date.** Each case's own `submitted_on` serves as "today" in the prompt and in the date checks (decision D8). Results therefore do not depend on the day the run happens. The DA run used the Asia/Kolkata date at run time; that is unnecessary here because the authored dates are absolute.

## 6. Measurements (pre-registered definitions)

**Conventions:**

- **Detection:** FLAG_FOR_REVIEW or REJECTED. NEEDS_MORE_INFORMATION and ELIGIBLE_PENDING_CONFIRMATION are never detections.
- **Group-level rates (primary):** each label cluster contributes its majority outcome, with Wilson 95% intervals (`group_uncertainty.py`).
- **Case-level rates:** cluster-bootstrap intervals (5,000 replications, seed 20261116); ICC and effective sample size are also reported.
- **Primary analysis:** intent-to-treat. Every case is included, and a Gemini failure becomes VERIFICATION_ERROR, which is neither a detection nor an approval.
- **Secondary analysis:** the complete-case subset, where Gemini returned a valid answer.

| # | Measurement | Definition | Role |
|---|---|---|---|
| M1 | Fraud recall | F cases detected ÷ F cases | Primary |
| M1b | Fraud held before activation | F cases not reaching VERIFIED_ACTIVE after simulated confirmation ÷ F cases | Secondary (end to end) |
| M2 | False-positive rate | Legitimate (L + I) cases detected ÷ legitimate cases; borderline excluded | Primary |
| M3 | Precision | Detected F ÷ (detected F + detected L/I) | Secondary. Sensitivity version adds detected B to the denominator |
| M4 | Legitimate approval rate | L cases APPROVED (i.e. ELIGIBLE_PENDING_CONFIRMATION) ÷ L cases | Secondary. Also over L + I, and after simulated confirmation (activation rate) |
| M5 | Information-request rate | NEEDS_MORE_INFORMATION ÷ cases, per stratum and overall | Secondary. L share = avoidable requests; I share = appropriate requests |
| M6 | Manual-review rate | FLAG_FOR_REVIEW ÷ cases, per stratum and overall | Secondary. Split by review basis: deterministic finding / document-supported model finding / unverified model suspicion |
| M7 | Unsafe provisional approvals | APPROVED where the case is F, B or I | Primary gate for I: must be 0. F and B reported by mechanism |
| M8 | Unsafe activations | Reaches VERIFIED_ACTIVE and any of: (a) F; (b) a required check not CONFIRMED by an independent source; (c) I; (d) activated without a confirmation record; (e) accepted on a campaign-supplied contact | Gates: (b)–(e) must be 0. (a) reported, with the environment caveat |
| M9 | API reliability | Per request: OK, SERVER_ERROR, TIMEOUT, RATE_LIMIT, QUOTA, INVALID_OUTPUT (schema, empty, truncated, blocked), AUTH/CONFIG. First-attempt success, coverage after retry, retries used, quota pauses, `modelVersion` changes | Secondary |
| M10 | Latency | HTTP-only seconds per successful request (pacing excluded): median, p90, p95, max; timeouts counted separately | Secondary |

**Also reported:**
- all rates by category, mechanism, keyword-free status, incomplete sub-type and review basis;
- paired differences between hybrid v3, hybrid v2 and V3 alone, with McNemar's test at group level;
- external contacts per 100 campaigns;
- retrieval coverage;
- κ;
- every misclassified group with its findings.

**Primary endpoints (no others are tested for significance):** M1, M2, M7 for stratum I, and M8 (b)–(e).

**Gates.** The gates are pass/fail safety invariants. Recall, FPR and precision are reported as estimates with intervals; no numeric targets are set unless approved in decision D9.

**Claims.** An improvement over hybrid v2 is claimed only if the group-level paired 95% interval excludes zero. Results apply only to the model, tier and retrieval mode actually used.

## 7. Provisional approval, final approval and activation

| Stage | State | How it is reached | What it allows |
|---|---|---|---|
| Automated decision | APPROVED → ELIGIBLE_PENDING_CONFIRMATION | Hybrid v3 finds no contradiction, no open item, supported financial evidence, and a clean Gemini answer | Nothing public. Authenticity UNCONFIRMED; no fundraising, no disbursement. Three confirmations are listed as pending. This is **provisional approval** |
| Confirmation | stays ELIGIBLE_PENDING_CONFIRMATION | A verifier records each check. A contradiction sends the campaign to FLAG_FOR_REVIEW; an unreachable or inconclusive contact leaves the check open; a campaign-supplied contact never satisfies a check | — |
| Final approval and activation | VERIFIED_ACTIVE | Only `record_confirmation`, when the last required check is CONFIRMED through an independent source. Automated verification and reviewers cannot set it, and the workflow raises `IllegalTransition` if anything tries | Campaign live; disbursement allowed. `activation_status` reports authenticity CONFIRMED_BY_INDEPENDENT_SOURCES |
| Review | FLAG_FOR_REVIEW | A contradiction, a model warning, or a post-activation suspension | A reviewer may clear the campaign back to pending, which resets every check; they cannot activate it |

**Final approval and activation are currently the same event.** They are a single state in the frozen workflow, and disbursement is allowed in it.

**Recommended future change (decision D10, needs a new version):**
- separate *activation*, when fundraising opens after the identity, institution and payee confirmations;
- from *disbursement*, which is released in tranches to the institution's verified account against invoices, after the amount confirmation (Appendix A).

The evaluation measures each existing stage separately: M4/M7 at provisional approval, M8 at activation.

## 8. API budget (recommended; requires approval, D2)

| Stage | Calls | Purpose |
|---|---|---|
| 0. Offline dry run | 0 | Fake transport on the pilot cases only. The sealed test set is parsed and validated, but no decisions on it are computed or displayed before the live run |
| 1. Pipeline pilot | ≤ 8 (6 cases + 2 retries) | 6 extra cases written by the authors for the pilot, excluded from every analysis, never used to change any frozen component |
| 2. Main run | N + ⌈0.10 N⌉ | One generation call per case, plus one retry for at most 10% of cases |
| Embeddings | 0 | Lexical retrieval (D3). Embedding retrieval would add about 6 calls per case |
| **Total at N = 540** | **≤ 602 generation calls, 0 embedding calls** | Hard cap enforced by the transport |

**Not included, each needing separate approval:**
- the production-prompt comparator: +N calls;
- a reliability-only probe of the production default `gemini-3.8-flash`, measured at 17% success and about 175 s latency in earlier runs: about 20 calls.

**Schedule.** On the free tier (20 requests a day for `gemini-3.6-flash`), 602 calls take at least 31 days. Quota pauses would also dominate the reliability figures. A paid tier would take hours, but reliability results would then apply to that tier only.

## 9. Stopping rules (pre-registered)

**Stop permanently** (report as an incomplete run):

1. The approved cap is reached. The transport refuses the next request.
2. Any authentication, permission, model-not-found or invalid-request error. This is a configuration problem, so the run stops at the first one.
3. The hybrid v3 freeze, either earlier freeze, the sealed test set or the sealed labels fail verification at start or at any resume.
4. A pipeline integrity failure: a runner exception, a case that cannot be mapped, or an output-directory conflict.
5. After at least 100 requests, the cumulative transient-failure rate exceeds 25%, or the retry allowance (⌈0.10 N⌉) is used up. Coverage would then be too low to interpret.

**Pause, then resume with an identical configuration:**

6. **Quota exhaustion (daily 429).** Pause until the provider's reset (08:00 UTC on the free tier). Quota pauses are not model failures and are reported separately.
7. **Three consecutive transient failures** (5xx, timeout, connection), or more than 20% transient failures in the last 25 requests. Pause for at least 1 hour. After a third pause in one UTC day, wait for the next day.

**Retry policy.**
- At most one retry per case, and only after a transient failure, waiting 30 s or as long as Retry-After requires.
- No retry for invalid output, blocked output or configuration errors. These count as reliability failures, and the case becomes VERIFICATION_ERROR.

**Never stop on results.**
- No interim look at decisions, labels or accuracy, so there is no optional stopping.
- Interim status shows only calls used, failures by category and coverage.
- Safety-invariant violations (M7-I, M8 b–e) are results to report, not stopping triggers. No real campaign is affected, and stopping would bias the estimate.

**Other rules.**
- **Model drift.** If `modelVersion` changes during the run, both segments are reported separately.
- **Calendar limit.** If the run has not finished within 45 days of starting, it stops and is reported as partial.
- **Coverage threshold.** If valid Gemini coverage is below 90%, the Gemini-dependent results are reported as inconclusive. The intent-to-treat results still stand.

## 10. Order of work

1. Approve decisions D1–D11 (§12).
2. Build the v5 tooling with no API use:
   - validator: v4 checks plus the new strata, mechanisms, `COST_ISSUER`, the extended novelty list and the LLM-assisted flag;
   - budgeted runner with the stopping rules;
   - scorer implementing §6 exactly.

   Then test the tooling on synthetic toy data, freeze it with a hash manifest, and seal this protocol.
3. Recruit at least 3 authors, 2 labellers and 1 adjudicator, none of them involved in development. Brief them with the author or labeller kit only.
4. Authors write the pilot cases and the test cases. The coordinator then:
   - validates them;
   - seals the submission hash;
   - stores the file outside the developer's workspace.
5. Blind labelling, then κ, then adjudication, then sealing the labels.
6. Stage 0 (offline), then Stage 1 (pilot, ≤ 8 calls, with a pipeline-only review).
7. Stage 2 (main run). The runner verifies every freeze and seal, and refuses to reuse its output directory.
8. The scorer writes every metric before anyone looks at an individual case. Then the report is written, including every misclassified group, the redacted audit records, the API log summary and the provenance of each case.

## 11. Data protection

**Synthetic cases.** Synthetic by default, with invented people, phone numbers and accounts. Real institution names may be used only with the coordinator's approval, and never with invented misconduct attached.

**Real material.** De-identified real dossiers need all of the following before any external model sees them:
- consent;
- a data-processing agreement;
- redaction;
- the framework's data-authorisation guard.

Real and synthetic results are reported separately.

**Logs.** The API log never holds content or the key.

## 12. Decisions requiring approval before sealing

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Model under test | `gemini-3.6-flash`: the prompt and policy were developed on it, and it is the only model with acceptable measured reliability. Production default stays `gemini-3.8-flash` (unchanged); results then describe 3.6 only |
| D2 | API budget and tier | Hard cap N + ⌈0.10 N⌉ + 8 generation calls, 0 embeddings (≤ 602 at N = 540). Paid tier preferred; free tier means at least 31 days |
| D3 | Retrieval | Lexical top-5 with no embeddings, coverage reported. Differs from production embedding retrieval for cases with more than five chunks |
| D4 | Comparators | Hybrid v2 and V3 alone, both paired at zero extra cost. Exclude the production-prompt system (+N calls) |
| D5 | Amount confirmation | Keep v3 frozen; evaluate Appendix A as a pre-registered, simulated secondary analysis. Implementing it in the workflow would mean a new version and a new freeze before authoring starts |
| D6 | Authors and labellers | Human authors and labellers independent of development are required for an "independent" claim. LLM-assisted cases are a separate, non-primary stratum |
| D7 | Size | Full design: 270 groups, ≤ 540 cases. The reduced 150-group design widens recall intervals to about ±14 points |
| D8 | Reference date | Each case's `submitted_on` |
| D9 | Numeric targets | Gates only (M7-I = 0, M8 b–e = 0), plus estimates with intervals. No recall or FPR targets without an external basis |
| D10 | Policy changes for later versions | Appendix A amount confirmation; Appendix B assisted route and capped partial activation; separating activation from disbursement. None of these is in the frozen system |
| D11 | Stopping rules | As in §9 |

---

## Appendix A: independently confirming the requested amount (proposed procedure)

**Purpose.** Establish, through a channel the campaigner does not control, how much money the need actually requires. Then compare that figure with the goal before any money moves.

**Steps.**

1. **Identify the cost issuer.** This is the billing desk of the hospital, the institution's accounts office, or the supplier or contractor. The financial gate already extracts the issuer; the verifier confirms it.
2. **Source the contact independently.** Use an official directory or website, a state health-department list or the NABH directory, UDISE+ or AISHE for schools and colleges, the GST portal (GSTIN lookup) for suppliers, or NGO Darpan or the registrar for organisations. Contacts printed in the uploads are recorded but never sufficient, which is the same rule as the existing workflow.
3. **Ask blind.** Give the patient, student or project identifier and the document's reference number, and ask the issuer to *state*:
   - the estimated or outstanding amount;
   - amounts covered by insurance, PMJAY, scholarships, waivers or advances;
   - the account the issuer accepts payment into.

   Never read out the campaign's figure first. Record the stated amounts, the date, the contact source and the verifier ID.
4. **Compare.**
   - **Within tolerance:** the goal is at most (stated amount − other payers) × 1.05. Record CONFIRMED.
   - **Above that:** record CONTRADICTED. The campaign goes to review, where the goal can be capped at the confirmed figure with the campaigner's consent.
   - **Cannot disclose:** request the estimate directly from the issuer's official email to the platform, or obtain the beneficiary's signed disclosure consent.
   - **Unreachable:** the check stays open.
5. **Bind the money to the issuer.** Prefer direct payment to the issuer's verified account, with an account-holder name match and the directory as the source. Then even an overstated goal cannot leave the treating institution.
6. **Disburse in tranches.** For goals above an agreed threshold (for example ₹2 lakh), or long treatments, release money in tranches against invoices. Re-confirm when a confirmation is more than 30 days old at disbursement.
7. **Community and organisation campaigns.** Confirm that the supplier exists (active GSTIN, address) and confirm the quotation with the supplier. Where there are many suppliers, confirm the items covering at least 80% of the goal.
8. **Handle surplus.** State in advance how surplus is handled (refund, or transfer with donor consent).
9. **Privacy.** Collect disclosure consent at campaign creation, and share the minimum data needed.

**Gaps in the frozen version.**
- Medical and education institution checks already *describe* confirming the billed amount or fee demand, but the record holds no amount.
- Community checks confirm registration only.

Making this an explicit, recorded check is a workflow change, which means a new version (D5, D10). The evaluation measures it as a simulation, from the `COST_ISSUER` record:
- amount-inflation fraud caught;
- genuine cases wrongly contradicted;
- added contacts per 100 campaigns.

## Appendix B: fair review for genuine beneficiaries without formal cost quotations (proposed procedure)

**Principles.**
- A missing formal quotation leads to NEEDS_MORE_INFORMATION, never to rejection.
- The safety bar for activation does not change. What changes is who does the work to produce evidence and which evidence is accepted.

**Steps.**

1. **Triage.**
   - Within 1 working day.
   - Within 24 hours when the documents show treatment within 14 days, or the reviewer judges the case urgent.
2. **A specific request.** Written in plain language and in the campaigner's language, it names what is missing and lists the acceptable alternatives:

   | Category | Alternative evidence of cost |
   |---|---|
   | Medical | Government hospital's list of items to buy, with pharmacy or supplier quotes; the treating doctor's note naming the procedure, plus a billing-desk confirmation obtained by the platform; an insurance or PMJAY pre-authorisation showing covered and uncovered amounts; recent receipts for ongoing treatment (for example 3 months of dialysis) establishing the running cost |
   | Education | Official fee structure from the institution's website or prospectus; last term's receipt plus the current circular; a scholarship or waiver letter showing the balance; hostel or mess bills |
   | Community | Two supplier quotations; the government schedule of rates (for example PWD SOR) for construction items; invoices from a comparable earlier project |

3. **Assisted route.** A trained caseworker or a partner NGO obtains the amount independently from the institution, using the Appendix A procedure, so the family does not have to produce a document. The recorded, independently sourced figure substitutes for the quotation.
4. **Partial and direct options** (a policy change; D10):
   - activate a campaign capped at the independently confirmed amount, raising the cap later on new evidence;
   - or pay the institution directly against invoices.
5. **Reviewer rules.**
   - Reviewers cannot reject solely because a formal quotation is missing.
   - Any rejection needs two reviewers.
   - Reviewers see findings labelled by basis, and must not treat an UNVERIFIED_MODEL_SUSPICION as evidence.
   - Reasons are recorded from a fixed list.
   - Appeals go to a different reviewer and are decided within 5 working days.
6. **Time limits.**
   - A decision within 3 working days of receiving evidence.
   - A request never expires automatically. After 14 days without a reply, the campaigner gets a reminder and a phone call.
7. **Fairness monitoring.** Each month, compare information-request rates, time to activation, abandonment after a request, and legitimate approval rates across:
   - category;
   - government and private hospitals;
   - language;
   - state;
   - rural and urban beneficiaries;
   - beneficiary type.

   A ratio below 0.8 between groups triggers a policy review. This is a screening heuristic, not a legal test.
8. **Data minimisation and consent** throughout.

**In this evaluation**, the I(d) "genuine but informal" sub-type measures:
- how often these beneficiaries receive an information request rather than a flag;
- how many could be resolved through the assisted route, i.e. where the `COST_ISSUER` record would independently confirm an amount.
