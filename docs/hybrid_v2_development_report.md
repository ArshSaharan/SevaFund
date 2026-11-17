# Improved V3 + Gemini (hybrid v2): development report

**Status:** development only. Nothing was deployed and no production behaviour changed:

- `app/services/ai_verifier.py`, the production prompt, `app/config.py` and the production default model
  (`gemini-3.8-flash`) are byte-identical, which a test checks.
- **No Gemini API call was made in this round.**

**Frozen implementation:** `evaluation/hybrid_v2_freeze.json`.

- Policy `hybrid-v2-dev-1`, digest `00b8a03e36de1bd2`.
- Code commit `7bf795e`.
- 34 files hashed, covering the development Gemini package, the evaluation framework, frozen V3, the approval
  workflow, the independent-test runner and the production files.

> **Two kinds of results, never mixed**
> - **Development results (section 4):** in-sample. They re-score the Gemini outputs saved from the 10-case
>   evaluation, and the revised policy was designed *after* inspecting those outputs. They are not evidence
>   of improvement.
> - **Independent-test results (section 5):** not yet available. No independently authored, independently
>   labelled dataset exists yet. The frozen runner that will produce them is prepared and refuses to run
>   without one.

---

## 1. What changed

All changes are in `app/services/development_gemini_verification/`, a development-only package with no
production imports.

### Escalation policy (`policy.py`, `concerns.py`)

**How warnings are classified.** Every Gemini warning becomes one of five types:

| Type | Escalates? |
|---|---|
| Fraud indicator: altered document, cost already paid, another person's record, diverted payee | only if grounded |
| Contradiction | only if grounded |
| Information gap: missing, unverified or pending | never; becomes part of an information request |
| Date claim | checked against the deterministic date assessment |
| Other | never |

**What counts as grounded.** A fraud indicator or contradiction escalates only if it is tied to the
retrieved documents: either a quoted passage that occurs in the retrieved text, or, for free-text warnings,
a number or distinctive word that occurs in the documents and *not* in the campaign's own text.

**What escalates to review:**

1. V3's own contradictions;
2. genuinely future-dated documents;
3. Gemini's explicit FLAG or REJECT, capped at review, so Gemini never rejects on its own;
4. grounded contradictions, even when Gemini only asked for more information.

**What becomes a targeted information request:**

- information gaps;
- expired documents;
- ungrounded fraud-type warnings, which are shown to the reviewer but don't escalate.

**What never approves:**

- any verification failure (it becomes VERIFICATION_ERROR);
- any unresolved gap or unverified concern;
- any information request from V3 or Gemini.

**Approval** requires both V3 and Gemini to approve with nothing unresolved. Even then the campaign only
becomes `ELIGIBLE_PENDING_CONFIRMATION`: independent confirmation of the beneficiary, payment destination
and institution is still required before activation or any release of funds.

### Date handling (`dates.py`, `prompt.py`)

- **Deterministic classification.** Every document date is classified against a reference date (the
  submission date, or today's date):
  - **valid**;
  - **expired**: a "valid until" date has passed, or the document is older than 365 days;
  - **future**: an issue date later than the reference date plus a one-day grace period;
  - **mentioned**: due dates, scheduled appointments and planned events, which are never judged.
- **Vetoing spurious claims.** A model claim of a "future date" is vetoed when no document issue date is
  actually in the future.
- **The dated prompt** forks the production prompt and adds two things only:
  - a **verification-date section** stating today's date and the submission date, and defining
    "future-dated";
  - **categorised, quoted concerns**.

  All production response fields are kept.

### Reliability (`client.py`)

- **Failures never raise.** Every failure (API error, timeout, 503, quota exhaustion, invalid JSON, schema
  mismatch, truncation, safety block, unexpected exception, missing key) becomes a `FAILED` outcome with a
  sanitised category, and the policy turns that into `VERIFICATION_ERROR`.
- **Existing protections are preserved.** The default transport is the production `post_json`, with its
  bounded retries, Retry-After handling and daily-quota detection. Under evaluation, the budgeted transport
  makes exactly one request per call.
- **The production default model stays `gemini-3.8-flash`.** Evaluations select 3.6-flash only through a
  per-process override.

### Evaluation framework

There are two new opt-in configurations: `gemini_rag_dated` (one generation call, sharing retrieval) and
`hybrid_v2` (no call).

- **Existing configurations** and their saved experiments are unaffected.
- **Budgets, the stop rule and failure logging** apply unchanged to the dated call.

## 2. Tests

| Test file | Tests | Covers |
|---|---:|---|
| `tests/test_hybrid_v2.py` | 51 | Dates (valid, boundary grace day, future, explicitly expired, expired by age, scheduled and due events). Concern classification on newly written warning texts. Grounding by quote and by document-only facts. Every policy rule, including "an unverified concern blocks approval without escalating". An exhaustive check that nothing approves while anything is unresolved and nothing is ever activated. All eight client failure modes. The missing-key case. The default transport's retry setting. Production untouched. |
| `tests/test_gemini_evaluation_framework.py` | 25 | Including the two new configurations, shared retrieval, the dated prompt actually being sent, and a dated-call failure triggering the stop rule |
| `tests/test_independent_runner_v4.py` | 8 | Freeze verified; refusals for protocol failure, unsealed data, missing labels, unsealed labels, broken freeze and missing API approval; labels taken from adjudication, never from authors |

**Full suite:** 338 passed. The one failure, `test_campaign_verification_endpoint` (HTTP 401), predates
all of this work.

**What the newly written tests exposed.** These tests use warning wording written fresh, not copied from the
evaluation outputs, and on first run they found **two classifier misses**:

- "No … doctor's prescription was uploaded": the apostrophe broke the pattern;
- "Story says … unpaid, but the ledger shows a nil balance": the claim-versus-document form wasn't
  recognised.

They also found **one policy gap**: Gemini approves, but mentions an unverified forgery concern. All three
were fixed in general, not by matching those exact strings. A pattern classifier over model-written prose
remains a limitation (section 6).

## 3. Reliability and latency (unchanged by this round)

The revised policy re-uses the Gemini outputs from the 10-case run. It adds **no API calls and no latency**.
The figures are those of `runs/gemini_eval_v1_3_6`:

- **Success:** 19 of 20 generation calls (Wilson 95% interval 76–99%), with one HTTP 503 and no timeouts.
- **Latency:** mean 45.5 s, median 45.1 s, p95 72.5 s.

The dated prompt has **not** been run against the API, so its own reliability and latency are unmeasured.

## 4. Development results: in-sample, not evidence of improvement

**Run:** `evaluation/runs/hybrid_policy_rescoring_20261116T160320Z/` (machine-generated `report.md`). These
are the 10 saved cases: 4 fraudulent, 4 legitimate and 2 borderline.

- The replica of the existing rule reproduces all 9 recorded combined decisions.
- Re-running under the frozen code gives identical decisions.

### Fraud detection and false positives, reported separately

Detection means FLAG_FOR_REVIEW or REJECTED. Information requests and pending confirmation are never
counted as detections.

| System | Recall (fraud detected) | False-positive rate | Precision | F1 |
|---|---:|---:|---:|---:|
| Original V3 | 2/4 = 50% (15–85%) | 0/6 = 0% (0–39%) | 100% | 67% |
| Existing V3 + Gemini | 4/4 = 100% (51–100%) | 4/6 = 67% (30–90%) | 50% | 67% |
| **Improved V3 + Gemini** | 3/4 = 75% (30–95%) | 0/6 = 0% (0–39%) | 100% | 86% |

### Safety and workload

| System | Unsafe approvals (fraud or borderline approved) | Legitimate escalated | Manual reviews | Information requests | Verification errors | Approved → pending confirmation |
|---|---:|---:|---:|---:|---:|---:|
| Original V3 | 3 (V3T-064, V3T-084, V3T-194) | 0 | 2 | 2 | 0 | 6 |
| Existing V3 + Gemini | 0 | 2 | 8 | 0 | 1 | 1 |
| **Improved V3 + Gemini** | 0 | 0 | 3 | 5 | 1 | 1 |

### Every change, explained

| Case | Label | Existing → improved | Why |
|---|---|---|---|
| **V3T-064** | fraudulent (consistent fabricated paperwork) | FLAG → NEEDS_MORE_INFORMATION | **Regression in detection.** The existing system escalated because Gemini attached three warnings to an information request. The first, a "future date (07 September 2026)", is refuted by the documents (submitted 30 Oct 2026) and is now vetoed. The other two are generic gaps. Nothing in the dossier reveals the fabrication, so the case is no longer *detected*, but it is still **not approved**: it gets a targeted information request, and activation would also need external confirmation. |
| V3T-084, V3T-194 | borderline | FLAG → NEEDS_MORE_INFORMATION | Gemini's warnings were information gaps (unconfirmed net balance; a cropped screenshot without a date or seal). An information request is the protocol's intended outcome for borderline cases, and neither is approved (V3 alone approved both). |
| V3T-024 | legitimate | FLAG → NEEDS_MORE_INFORMATION | The "landlocked city with a water crossing" warning is not grounded in the documents (it comes from the story and general knowledge), so it becomes an unverified concern rather than an escalation. The case is still not approved, because Gemini asked for diagnosis records. That is legitimate-campaign friction, not a false fraud flag. |
| E150-102 | legitimate (incomplete evidence) | FLAG → NEEDS_MORE_INFORMATION | Its final authorisation is pending, so an information request is the expected outcome. |
| V3T-104 | legitimate | VERIFICATION_ERROR (unchanged) | Gemini returned a 503. Both systems refuse to approve; it must be re-run. |

**Net, in-sample:**

- legitimate escalations fell from 2 to 0, and manual reviews from 8 to 3;
- unsafe approvals stayed at 0;
- recall fell from 4/4 to 3/4 (the V3T-064 regression above);
- information requests rose from 0 to 5.

The extra information requests are workload moved, not removed: 2 legitimate, 1 fraudulent and 2 borderline
cases now wait for documents instead of a reviewer.

## 5. Independent-test results: not yet available

**Nothing in this repository is an independent test of hybrid v2.** The prerequisites are:

1. **An independently authored and labelled v4 dataset.** It is produced by people who have not seen the
   verifier, following `evaluation/independent_test_v4/AUTHORING_GUIDE.md`, with two blind labellers,
   adjudication and Cohen's κ. Each submission is validated and sealed with
   `evaluation/validate_independent_submission.py`.
   - **I cannot produce this.** As the developer of the verifier, any cases or labels I wrote would not be
     independent.
2. **API approval and a budget.** With configurations `heuristics_lexical, gemini_rag, hybrid,
   gemini_rag_dated, hybrid_v2`, each case costs 2 generation calls and 1 embedding call.
3. **A one-time run** with `evaluation/run_independent_test_v4.py`. It refuses to run unless all of the
   following hold:
   - the hybrid-v2 freeze verifies;
   - the dataset passes the protocol and matches its seal;
   - the adjudicated labels cover every case and match their seal;
   - API approval is given.

   It refuses to run twice, and `--plan` shows the call budget with no network access.

When it runs, the report will give, on group-level units, the same metrics for original V3, existing
V3 + Gemini and improved V3 + Gemini: precision, recall, F1, false-positive rate, unsafe approvals, manual
reviews, information requests, API reliability and latency.

## 6. Remaining limitations

1. **The development evidence is in-sample and tiny.** There are 10 cases, the policy was designed on them,
   and one case moves recall by 25 points. No difference above is statistically meaningful.
2. **The dated prompt is untested against the live API.** Its effect on Gemini's decisions, its reliability
   and its latency are unknown; only the deterministic date veto was exercised.
3. **The classifier is pattern-based.** It reads model-written prose with patterns. Newly written test texts
   already exposed two misses, and other wordings will exist. The dated prompt's structured, quoted concerns
   are meant to reduce reliance on this classifier, but they have not been observed in live output.
4. **The grounding heuristic is weak evidence:**
   - a model can cite a real number from a document and misinterpret it;
   - a campaign can quote its own documents in the story, which hides genuine contradictions from the
     "document-only facts" test.
5. **Consistent fabrication is undetectable from the dossier.** The V3T-064 regression shows the improved
   policy no longer escalates on generic warnings. Only external confirmation can catch such cases.
6. **Latency** (mean 45.5 s, p95 72.5 s) is suitable only for an asynchronous check, not for synchronous
   submission.
7. **Reliability** (19/20) does not yet establish a ≥95% success rate.
8. **Information-request workload** rose to 5 of 10 in-sample. Legitimate campaigns with incomplete evidence
   now wait for documents.
9. **Data.** All data so far is synthetic and single-author. Independent labels require people.

## 7. Decisions that need the owner's approval

1. **Production behaviour.** Should the dated prompt, the revised escalation policy and safe failure
   handling be ported to the production verifier? Not recommended before the independent test.
2. **API budget** for a development run of the dated prompt (for example 10 generation calls on
   synthetic cases outside the 10 already used). It would check live behaviour (dates, structured concerns,
   latency) before the independent test. It would be development evidence only.
3. **People** for the v4 dataset: authors, two labellers, an adjudicator and a coordinator.

## 8. Reproduction

```bash
./.venv/bin/python -m pytest -q tests/test_hybrid_v2.py tests/test_gemini_evaluation_framework.py tests/test_independent_runner_v4.py
./.venv/bin/python -B evaluation/freeze_hybrid_v2.py verify
./.venv/bin/python -B evaluation/rescore_hybrid_policies.py          # in-sample development re-scoring, no API call
./.venv/bin/python -B evaluation/run_independent_test_v4.py <submission.jsonl> --seal <seal.json> \
    --labels <adjudicated.csv> --label-seal <labels_seal.json> --plan  # once a sealed v4 dataset exists
```
