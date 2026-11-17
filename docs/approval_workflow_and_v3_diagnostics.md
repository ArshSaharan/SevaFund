# Approval workflow, V3 diagnostics, group-level analysis and Gemini framework

**Status:** development only. Nothing here is imported by production code, and nothing was deployed
or committed. Frozen V3 (`ba1b045e…a7cd`) and frozen V2 (`a054be91…6fc6`) are unchanged; their freeze
checks pass. The production verifier, rules, RAG and config files, and all benchmark datasets, still
match their recorded hashes. No Gemini or paid API call was made.

All data used here are **synthetic and single-author**. None of these numbers are real-world
performance.

---

## 1. Decision 1: approval policy `ELIGIBLE_PENDING_EXTERNAL_VERIFICATION`

**Code:** `app/services/development_approval_workflow/`. It is a separate layer that consumes V3's
automated decision; the frozen V3 package is untouched.
**Tests:** `tests/test_approval_workflow.py` (35 tests).

### States

| State | Reached from | Meaning | Funds |
|---|---|---|---|
| `ELIGIBLE_PENDING_CONFIRMATION` | V3 `APPROVED`; a reviewer clearing a flag; successful re-verification | Automated checks passed. Independent confirmation is required. | blocked |
| `NEEDS_MORE_INFORMATION` | V3 `NEEDS_MORE_INFORMATION` | Essential information is missing; a targeted request is sent. Not a fraud finding. | blocked |
| `FLAG_FOR_REVIEW` | V3 `FLAG_FOR_REVIEW`; a confirmation that **contradicts** a material fact; suspension of an active campaign | An unresolved material contradiction needs a human reviewer. | blocked |
| `VERIFIED_ACTIVE` | **only** `record_confirmation`, once every required check is confirmed through an independent contact | Live campaign. | **allowed** |
| `REJECTED` | V3 `REJECTED`; reviewer decision | Terminal. | blocked |
| `VERIFICATION_ERROR` | V3 `VERIFICATION_ERROR`; any unrecognised automated decision | Must be re-run; can never be approved directly. | blocked |

### Rules enforced by code and tests

- **Automated verification can never produce `VERIFIED_ACTIVE`.** The transition table and a guard
  in `_move` reject it.
- **Required confirmations:**
  - always the **beneficiary** and the **payment destination**;
  - plus the **institution**: the treating hospital (medical), the educational institution
    (education), or the registering authority (community or NGO).
- **A confirmation counts only if obtained through an independently established contact:** an
  official registry, an official directory, platform KYC, or a previously verified record.
  - Campaign-supplied contacts are recorded but never sufficient.
  - A phone number or e-mail that appears in the campaign's own uploads is automatically downgraded
    to campaign-supplied, whatever source the verifier selected.
- **Outcomes of a confirmation attempt:**
  - `CONTRADICTED` → `FLAG_FOR_REVIEW`;
  - `UNREACHABLE` or `INCONCLUSIVE` → the check stays open.
- **Reviewers cannot activate a campaign.** Clearing a flag returns it to pending, and any earlier
  confirmations are voided.
- **Pending confirmation is not a fraud detection.** `is_fraud_detection` is true only for review
  and rejection.
- **Every transition** is appended to `history` with its actor, trigger and reason.
- **Exhaustive test:** across every sequence of up to three confirmation attempts (each check, each
  outcome, independent or campaign-supplied), funds are released only when all three checks were
  independently confirmed and none was contradicted.

### Safety and workload, reported separately

On the 300-case synthetic final test, using saved V3 predictions:

| | V2 | V3 |
|---|---:|---:|
| **Safety:** automatic activations | 0 | 0 |
| **Safety:** fraud detected (review or reject) | 50 | 60 |
| **Safety:** fraud held pending external confirmation | 0 | 20 |
| **Safety:** borderline held pending confirmation | 0 | 20 |
| **Workload:** manual reviews | 50 | 60 |
| **Workload:** information requests | 250 | 100 |
| **Workload:** external confirmations required | 0 | 420 |
| **Workload:** legitimate campaigns delayed by avoidable requests | 100 | 0 |

**The 20 fraudulent cases V3 used to auto-approve are now held, not detected.** Whether they are
eventually stopped depends on the quality of external confirmation, which no offline dataset
measures.

**Sensitivity (an assumption, not a measurement):** if confirmation misses 5%, 20% or 50% of pending
fraud, the expected fraudulent activations are 1, 4 or 10.

## 2. Decision 2: frozen V3 on the previously used diagnostic benchmarks

**These are previously used diagnostic datasets, not fresh independent tests.** All three were
inspected in earlier cycles.

**Run:** `evaluation/runs/diagnostic_v3_prior_benchmarks_ba1b045e8b9d/`. V3 was executed once. The
runner verifies every freeze first, guards against Gemini calls, refuses re-runs, and writes output
only after every engine has finished.

**Provenance of each engine's results:**
- **V3:** executed here.
- **V2:** saved predictions of frozen V2.
- **V1:** saved on the 150-case set. On the 200- and 100-case sets no paired V1 result existed, so
  frozen, hash-verified V1 was executed here under its original top-5 lexical-retrieval protocol.
- **Baseline:** saved results from the same frozen code.

**Conventions:**
- Fraud is the positive class; legitimate and borderline cases are negatives.
- A detection is FLAG_FOR_REVIEW or REJECTED. V1 and the baseline also count an emitted red flag,
  as in their original evaluations.
- An information request is not a detection.

### 200-case set (24 groups; the baseline's rules were revised on this very set, so its row is in-sample)

| Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit approved | Manual review | Info request | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 76.2% | 100.0% | 86.5% | 20.8% | 0.0% | 100.0% | 29.5% | 13.0% | 0.0% |
| V1 | n/a | 0.0% | 0.0% | 0.0% | 15.0% | 100.0% | 0.0% | 51.5% | 0.0% |
| V2 | 100.0% | 25.0% | 40.0% | 0.0% | 0.0% | 0.0% | 10.0% | 90.0% | 0.0% |
| V3 | 100.0% | 25.0% | 40.0% | 0.0% | 0.0% | 100.0% | 10.0% | 50.0% | 0.0% |

### 100-case set (100 single-case groups)

| Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit approved | Manual review | Info request | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 40.0% | 95.0% | 56.3% | 95.0% | 5.0% | 2.5% | 95.0% | 0.0% | 0.0% |
| V1 | 100.0% | 7.5% | 14.0% | 0.0% | 22.5% | 20.0% | 3.0% | 79.0% | 0.0% |
| V2 | 75.0% | 7.5% | 13.6% | 1.7% | 0.0% | 0.0% | 4.0% | 96.0% | 0.0% |
| V3 | 75.0% | 15.0% | 25.0% | 3.3% | 20.0% | 15.0% | 8.0% | 77.0% | 0.0% |

### 150-case set (45 label clusters)

| Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit approved | Manual review | Info request | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 14.1% | 20.0% | 16.6% | 81.1% | 80.0% | 25.0% | 56.7% | 0.0% | 0.0% |
| V1 | 100.0% | 26.7% | 42.1% | 0.0% | 46.7% | 63.3% | 10.7% | 37.3% | 2.7% |
| V2 | 100.0% | 16.7% | 28.6% | 0.0% | 0.0% | 0.0% | 6.7% | 93.3% | 0.0% |
| V3 | 100.0% | 16.7% | 28.6% | 0.0% | **60.0%** | 75.0% | 6.7% | 39.3% | 0.0% |

Category-wise results are in the run's `report.md`.

### Group-level view (V3)

| Dataset | Fraud groups flagged (95% CI) | Fraud groups auto-approved | Legit groups approved | Recall, cluster bootstrap 95% CI |
|---|---|---:|---:|---|
| 200 | 2/11 (5–48%) | 0/11 | 6/6 | 0–54% |
| 100 | 6/40 (7–29%) | 8/40 | 6/40 | 5–28% |
| 150 | 2/15 (4–38%) | 5/15 | 15/15 | 0–37% |

### What this shows

1. **V3 did reduce information requests on the old sets:**
   - 200 cases: from 90% to 50%;
   - 100 cases: from 96% to 77%;
   - 150 cases: from 93% to 39%.

   It now approves legitimate campaigns: 100% on the 200-case set and 75% on the 150-case set.
   That was the follow-up problem the V3 task targeted, and it is substantially fixed on two of the
   three sets. On the 100-case set, 77% of cases still receive information requests; there, 77 of
   them lack critical claim support.
2. **V3 barely improved fraud detection on the old sets.** Recall equals V2 on the 200- and
   150-case sets (2 fraud groups each) and rises from 7.5% to 15% on the 100-case set.
3. **V3's relaxed evidence policy approves fraud on the old sets:**
   - 60% of the 150-case set's fraud, which is more than V1's 46.7%;
   - 20% of the 100-case set's fraud.

   Under the approval workflow, these become **pending external confirmation, not activations**:
   36 and 8 cases respectively.

   This is the strongest evidence that Decision 1 is necessary.

## 3. Group-level evaluation of the 300-case final test and the V3 development set

**Run:** `evaluation/runs/group_level_v3_20261116T103923Z/`. It is built from saved predictions; no
verifier was executed. **Statistics:** `evaluation/group_uncertainty.py`.

**Unit:** the label cluster (scenario family × label). The analysis reports:

- cluster-level rates with Wilson intervals;
- case-level rates with cluster-bootstrap intervals (5,000 resamples, stratified by label, fixed
  seed);
- ICC by the ANOVA estimator;
- the Kish effective sample size.

| 300-case final test | V2 | V3 |
|---|---:|---:|
| Clusters in which every case received the same decision | 30/30 | 30/30 |
| Detection ICC / effective sample size | 1.0 / 30 | 1.0 / 30 |
| Recall, with naive case-level CI | 50% (40–60%) | 60% (50–69%) |
| Recall, with cluster-bootstrap CI | 50% (20–80%) | 60% (30–90%) |
| Fraud clusters flagged | 5/10 (24–76%) | 6/10 (31–83%) |
| Fraud clusters auto-approved | 0/10 | 2/10 (6–51%) |
| Legitimate clusters approved | 0/10 | 10/10 (72–100%) |
| Borderline clusters approved | 0/10 | 2/10 (6–51%) |

**The V3 development set** (180 cases) behaves the same way: 18 clusters, ICC 1.0, effective sample
size 18. V3's recall there is 50%, with a cluster-bootstrap interval of 17–83%.

**Conclusion.** Treating the 300 cases as independent understates uncertainty by roughly a factor of
three in interval width. The V2-to-V3 recall difference (5 versus 6 fraud clusters) is a single
cluster and is not statistically distinguishable.

## 4. Decision 3: Gemini evaluation framework, prepared and not executed

**Code:** `evaluation/gemini_evaluation_framework.py`.
**Tests:** `tests/test_gemini_evaluation_framework.py` (15 tests). Every test runs with the HTTP
client disabled and a fake Gemini transport.

| Configuration | What it runs | API calls per case |
|---|---|---:|
| `heuristics_only` | production local heuristics, no documents | 0 |
| `heuristics_lexical` | production local heuristics + lexical retrieval | 0 |
| `gemini_no_rag` | **production** Gemini prompt, campaign text only | 1 |
| `gemini_rag` | Gemini-embedding top-5 retrieval + production prompt | 2 |
| `hybrid` | frozen V3 + cached `gemini_rag`; Gemini can only escalate; approval workflow applied | 0 |

**Requirements met:**

- **Identical case IDs.** A deterministic, stratified sample (default: 2 per family and label, 60
  cases). The saved plan pins the IDs, and the framework refuses to resume an experiment with
  different IDs.
- **Caching.** Successes go to `cache.jsonl`, keyed by configuration, case, input fingerprint,
  dataset and model. A re-run makes no calls for cached jobs.
- **Resume after quota exhaustion.** `QUOTA_EXHAUSTED`, authentication or permission errors, a
  missing model, or an exhausted budget stop the run cleanly. `state.json` records the reason, and
  the same command resumes.
- **API failures recorded separately.** `failures.jsonl` holds only stage, category, status,
  exception type and duration: no prompt, no response text, no key (tested). The production
  verifier's silent local fallback is bypassed, so a Gemini failure is never counted as a Gemini
  result.
- **Retrieval measured independently of verification:**
  - document coverage and empty-retrieval rate, for lexical and for embedding retrieval;
  - recall@k and MRR when a dataset supplies `gold_evidence_titles`. Current datasets don't, and
    protocol v4 requires them.
- **Verification metrics** are computed on the paired-complete subset, with coverage per
  configuration.
- **Latency and reliability:** per-configuration success rate, failure categories, and mean, p50 and
  p95 latency.
- **Privacy.** Any dataset with rows not marked `synthetic: true` is refused unless an explicit
  `--data-authorization` reference is supplied. In that case, names (including given names on
  their own), phone numbers, e-mail addresses, IFSC codes and UPI handles are redacted before
  anything leaves the machine.
- **No accidental execution.** `plan` is the default and writes nothing. `execute` requires all of:
  - `SEVAFUND_GEMINI_EVAL_APPROVED=1`;
  - a configured key;
  - an explicit `--max-calls` budget.

  Every guard runs before anything is written. The framework never changes billing.

**Prepared plan:** 60 cases × 5 configurations; 120 generation calls and 60 embedding calls (180 HTTP
requests). At a 20-per-day limit this needs **6 days only if embeddings have their own per-model
quota, and 9 days if all requests share it**, before any failed requests (each consumes quota and is
retried later) and any other use of the key. *Corrected 2026-11-16: the original text gave only the
6-day figure; see `docs/confirmation_and_gemini_pilot.md`.* The configured model is
`gemini-3.8-flash`.

**When approved, run:**

```bash
SEVAFUND_GEMINI_EVAL_APPROVED=1 ./.venv/bin/python -B evaluation/gemini_evaluation_framework.py execute --max-calls 20
# repeat daily; then:
./.venv/bin/python -B evaluation/gemini_evaluation_framework.py report
```

**Caveat.** The default dataset is the 300-case final test, which V3 has already been evaluated on,
so the `hybrid` row is not an independent test of V3. Use it to measure Gemini's contribution and
reliability. For performance claims, run the framework on the protocol v4 dataset.

## 5. Recommendation for a genuinely independent final evaluation

The protocol is `evaluation/independent_test_protocol_v4.md`; its key requirements are:

- **Independent authorship.** Cases and labels come from people who have never seen the verifier,
  with two blind labellers per case, adjudication and Cohen's κ. Include de-identified real dossiers
  where consent and a data agreement exist.
- **Statistical power from groups, not cases.** At least 225 scenario groups with 1–3 varied cases
  each, including about 90 fraud groups, which gives roughly ±10 points on recall. Analysis is
  pre-registered at group level.
- **Every fraud pattern you listed, in every category:**
  - internally consistent fabrication;
  - contradictions with independent records;
  - suspicious payees;
  - keyword-free fraud, enforced by `evaluation/check_keyword_free_fraud.py`;
  - prose contradictions.

  Also included: legitimate campaigns with incomplete documentation.
- **A simulated external-contact environment for each case**, including campaign-supplied contacts
  that lie. This makes it possible to measure what the approval workflow exists for: fraud reaching
  `VERIFIED_ACTIVE`, and the contact workload.

## 6. Unresolved limitations

1. **Every dataset so far is synthetic and written by one author.** No independent or real labels
   exist, so no figure in this repository is a real-world estimate.
2. **The workflow's safety rests on external confirmation, which has not been measured.** The
   policy guarantees that nothing activates automatically and that campaign-supplied contacts never
   suffice. Whether real verifiers actually catch fabricated dossiers through independent contacts
   is unknown until protocol v4's contact environment, or a real pilot, measures it.
3. **Workload moves rather than disappears.** V3 plus the workflow cuts information requests but
   adds 1.4–1.6 external confirmations per campaign: 420 per 300 on the final test, and 243 per
   150 on the old 150-case set. No staffing or cost model exists yet.
4. **V3's fraud detection did not generalise to the old corpora** (2 of 15 and 2 of 11 fraud
   groups). Its relaxed evidence policy approves fraud that V2 merely deferred.
5. **Sample sizes are small.** There are 10–40 fraud clusters per dataset. Differences of one or two
   clusters between versions are within noise.
6. **Approval in contact-driven checks:** an independently established contact can still be spoofed
   or compromised. The workflow records the source but cannot verify it.
7. **Gemini remains entirely unmeasured.** The framework is ready but not executed, and its default
   dataset is not independent of V3.
8. **No production integration was attempted.** The routers' current mapping (any red flag sets the
   status to FLAGGED, and auto-approval activates) is unchanged.

## 7. Reproduction

```bash
./.venv/bin/python -m pytest -q tests/test_approval_workflow.py tests/test_gemini_evaluation_framework.py
./.venv/bin/python -B evaluation/verify_candidate_v3_freeze.py
./.venv/bin/python -B evaluation/analyze_group_level_v3.py                     # saved predictions only
./.venv/bin/python -B evaluation/gemini_evaluation_framework.py plan           # no network
# evaluation/diagnose_v3_on_prior_benchmarks.py was a one-time run; it refuses to re-run into the same directory.
```
