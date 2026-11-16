# SevaFund development verifier V3: consolidated results and assessment

**Status:** development only. Not deployed, and no router or production file imports it.
**Frozen candidate:** `sevafund-development-candidate-v3.0`

- Package hash: `ba1b045e…a7cd`
- Configuration hash: `3835a9c2…e9`
- Freeze manifest: `evaluation/development_candidate_v3_freeze.json`, frozen 2026-11-16 10:07 UTC.

**Provenance.** Codex implemented V3, its datasets and runners, and executed every run cited here.
Its session ended at the usage limit during the closing regression and freeze checks, before any
written summary. This document completes that step. It adds read-only analysis of the saved
predictions and does **not** modify V3, re-run the final test, or change any dataset.

All results are offline and deterministic, on **synthetic** data. No Gemini, embedding,
semantic-RAG or paid call was made. Nothing here is a real-world accuracy estimate.

---

## 1. State verified at completion (2026-11-16)

| Check | Result |
|---|---|
| `evaluation/verify_candidate_v3_freeze.py` | valid: V3 package, configuration, V3 development dataset and V2 package all match |
| V2 package against its own freeze manifest | unchanged (`a054be91…6fc6`) |
| Production verifier, fraud rules, RAG, config, schemas, and the V1 candidate | byte-identical to the 150-case freeze (`assert_frozen()` passes) |
| 200-, 100-, 150-case, V1 and V2 development datasets | SHA-256 unchanged |
| Full test suite | 199 passed, 1 failed. The failure is `test_campaign_verification_endpoint` (HTTP 401), which predates all verifier work. |

## 2. What V3 changes relative to V2

V3 is a separate package, `app/services/development_verifier_v3/`, that extends V2's seven-stage
pipeline. The main changes are:

**Money parsing (`money.py`)**
- Amounts are `Decimal` values with an explicit currency: INR/₹/Rs, USD/$, GBP/£, EUR/€ and others.
- Written amounts are parsed ("two lakh fifty thousand").
- There is **no implicit exchange-rate conversion**: `verified_fx_rates` is empty by design, and
  amounts in different currencies are never compared.
- Malformed values remain invalid evidence; they are never treated as zero.
- This fixes V2's known failure, where `GBP 4,000.00` was read as ₹4,000.

**Evidence tiers (`evidence_policy.py`)**
- Missing evidence is split into *critical* and *optional*.
- Only critical gaps trigger an information request: beneficiary identity, payment destination, or
  a material claim.
- Optional evidence is advisory.

**Quantitative consistency (`quantitative_consistency.py`)**
- Durations and quantities tied to the same unit are compared across the campaign and its uploads,
  for example a twelve-month course against a ten-week calendar, or 40 kits requested against 24
  delivered.

**Revised uncertainty and decision handling (`decision.py`)**
- Missing optional evidence never creates a follow-up request.
- Errors still cannot become approvals.

Every component can be switched off for the ablation study (`enable_*` flags in `config.py`).

## 3. Development evaluation: V2 vs V3 on the V3 development set

**Corpus.** `evaluation/development_scenarios_v3.jsonl`: 180 cases, 60 per category; 60 legitimate,
60 fraudulent and 60 borderline. It is split by scenario family into a development part (90) and a
held-out part (90).

**Run.** `evaluation/runs/development_v3_frozen_20261116T100612Z/`.

**Convention change.** Binary metrics here **exclude borderline cases**. My V2 report counted them
as negatives, so these numbers are not directly comparable with that report's tables.

| Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2 | 100.0% | 16.7% | 28.6% | 0.0% | 0/60 | 0/60 | 5.6% | 94.4% | 0 |
| V3 | 100.0% | 50.0% | 66.7% | 0.0% | 30/60 | 60/60 | 16.7% | 33.3% | 0 |

**The held-out split did not test contradiction detection.** All three fraud families that contain
a visible contradiction sit in the *development* part, and V3 flags all 30 of those cases. All three
"internally consistent but fabricated" families sit in the *held-out* part, and V3 approves all 30
of those cases. So:

- the 100% development-split recall and the 0% held-out recall reflect how the families were
  placed, not how well V3 generalises;
- the development evaluation **never measured contradiction detection on unseen families**. Only
  the final test (section 5) does.

## 4. Ablation: V3 development set, identical 180 cases

| Variant | Recall | Fraud auto-approved | Manual review | Info request |
|---|---:|---:|---:|---:|
| full V3 | 50.0% | 30 | 16.7% | 33.3% |
| without category awareness | 50.0% | 30 | 16.7% | 27.8% |
| without cross-document checks | 0.0% | 30 | 0.0% | 50.0% |
| without improved financial parsing | 50.0% | 10 | 16.7% | 72.2% |
| without tiered evidence requirements | 50.0% | 0 | 16.7% | 83.3% |
| without revised uncertainty policy | 50.0% | 0 | 16.7% | 83.3% |

How to read this:

- **Cross-document checks** supply all of V3's fraud detection.
- **The workload reduction and the new fraud auto-approvals are the same effect.** Switching off
  the tiered evidence policy, or the revised uncertainty policy, brings fraud auto-approvals to 0,
  but information requests climb back to 83%. The relaxed policy that cuts information requests is
  exactly what turns the fabricated dossiers from "needs more information" into "approved".
- **Improved financial parsing** also cuts information requests (from 72% to 33%) by letting more
  cost documents qualify, which adds 20 fraud auto-approvals.
- **Category awareness** has no measurable effect on detection in this corpus.

## 5. One-time final test: V2 vs frozen V3

**Corpus.** `evaluation/final_test_scenarios_v3.jsonl`: 300 synthetic cases, 100 per category;
100 legitimate, 100 fraudulent and 100 borderline. It forms 30 families of 10 cases each and was
generated after the freeze.

**Run.** `evaluation/runs/final_test_v3_31f16ae955c4/`. Borderline cases are excluded from the
binary metrics.

| Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Reject | Errors | Mean / p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2 | 100.0% | 50.0% | 66.7% | 0.0% | 0/100 | 0/100 | 16.7% | 83.3% | 0.0% | 0 | 2.59 / 5.34 |
| V3 | 100.0% | 60.0% | 75.0% | 0.0% | 20/100 | 100/100 | 20.0% | 33.3% | 0.0% | 0 | 2.74 / 5.07 |

**Three-class dispositions:**

| Label | V2: approved / flagged / unresolved | V3: approved / flagged / unresolved |
|---|---|---|
| legitimate | 0 / 0 / 100 | 100 / 0 / 0 |
| fraudulent | 0 / 50 / 50 | 20 / 60 / 20 |
| borderline | 0 / 0 / 100 | 20 / 0 / 80 |

**Category-wise recall:**

| Engine | Medical | Education | Community |
|---|---:|---:|---:|
| V2 | 66.7% | 25.0% | 66.7% |
| V3 | 66.7% | 50.0% | 66.7% |

### The effective sample size is 30 families, not 300 cases

From read-only analysis of `case_level_predictions.csv`: every one of the 30 families received
**one identical decision for all 10 of its cases, under both engines**. The ten variants within a
family never produce different outcomes. These cases are not independent observations, so every
result should be read per family:

| Measure | V2 | V3 |
|---|---:|---:|
| Fraud families flagged | 5 of 10 | 6 of 10 (95% Wilson interval 31–83%) |
| Contradiction-bearing fraud families flagged | 5 of 8 | 6 of 8 (41–93%) |
| Fabricated fraud families auto-approved | 0 of 2 (both unresolved) | 2 of 2 |
| Legitimate families approved | 0 of 10 | 10 of 10 |
| Borderline families approved | 0 of 10 | 2 of 10 |

Read as 300 independent cases, V3's recall interval would be 50–69%. That is far narrower than the
evidence supports.

### Family-level changes from V2 to V3

**Gains:**
- `dispatch_quantity_diverges` (community) and `equipment_dispatch_shortfall` (education): from
  "needs more information" to flagged. These are the new quantity-consistency checks working.
- All 10 legitimate families: from "needs more information" to approved. This is the
  workload reduction the task asked for.

**Regression:**
- `supplier_ledger_closed` (community): V2 flagged it; V3 sends it to "needs more information".

**Still missed by both:**
- `credential_calendar_shortfall` (education): "needs more information" under both engines.

**New unsafe approvals:**
- `internally_consistent_but_forged_clinic_file` (medical) and `consistent_bursary_papers_forged`
  (education): V2 sent these to "needs more information"; V3 approves them.
- `account_image_without_issue_date` and `family_cost_share_unclear` (borderline): V3 approves both.

### Fraud auto-approval analysis

All 20 of V3's fraudulent auto-approvals are dossiers that are internally consistent but
fabricated. Their falsity is known only from the author's hidden provenance; no contradiction
exists in the text. No offline, dossier-only verifier can detect them. Only issuer confirmation,
registry lookups or payout checks could.

V2 approved none of them because V2 approved **nothing**: every legitimate case also went to an
information request. V2's 0% fraud auto-approval rate therefore says nothing about its safety.

### Execution audit (from the run's `metadata.json`)

The final run hit two problems in the runner, not the verifiers:

1. **First attempt:** stopped after one V2 case because of a schema mismatch (a missing `split`
   field). No results were saved.
2. **Second attempt:** completed and saved all 600 predictions, then failed while exporting the CSV.

`finalize_final_test_v3.py` rebuilt the CSV and report from those saved predictions without
calling either verifier again. The freeze was verified before and after this recovery.

## 6. Workload analysis

**Why V2 sent nearly everything to an information request.** V2 required an attributable cost
document (one with at least two of: issuer, date, reference, signatory), plus category-specific
documents, before it would approve. On evidence written as summaries, those requirements are never
met. This is the cause identified in the V2 report (cost evidence unmet in 138 of 140 requests on
the 150-case set).

**What V3 changed.** V3 asks only for critical evidence, which cuts information requests from about
83–94% to 33% on V3's own data.

**What it cost.** As the ablation shows, the relaxation is also what auto-approves fabricated
dossiers and two borderline families. V3 moves workload away from reviewers, and that cost falls
on safety. The gain in fraud detection is separate and comes from the quantity-consistency checks.

## 7. Limitations that affect every V3 claim

1. **Single synthetic author.** Codex wrote V3, both of its corpora and every label; there was no
   independent author and no human adjudication. The final-test generator was also written and
   edited during V3 development, before the freeze (its corpus was generated only after the freeze).
   The final test is therefore *post-freeze* but not *independent*.
2. **The template structure limits statistical power.** There are 30 effective units, and outcomes
   never vary within a family. Case-level percentages overstate certainty.
3. **The development hold-out did not hold out contradiction fraud.** Generalisation was measured
   once, on the final test: 6 of 8 contradiction families flagged.
4. **The old problem was never re-measured.** The task's headline problem was 100% follow-up on the
   200-, 100- and 150-case corpora, and V3 was **not** run on those corpora. Whether V3 fixes that
   specific problem is unmeasured.
5. **Consistent fabrication is undetectable offline** and is now auto-approved. Production use
   would need issuer, registry, identity and payout verification before funds are released.
6. **The Gemini experiment in section 12 of the V3 task was not prepared.** That covers heuristics
   alone, heuristics with lexical retrieval, Gemini with and without RAG, and the full hybrid. No
   Gemini-related V3 result exists.
7. **Changed convention.** Binary metrics exclude borderline cases, unlike the V2 report.
   Borderline approvals (20%) appear only in the three-class tables.

## 8. Assessment

**What improved**

- Information requests fell from about 83% to 33% on new synthetic families.
- Every legitimate family was approved, with no false positives.
- Two new kinds of contradiction are caught: duration and quantity.
- Multi-currency and written-amount parsing are now handled, with no implicit currency conversion.
- There were still no runtime errors.

**What remains unreliable**

- 20% of fraudulent cases (2 of 10 fraud families) and 20% of borderline cases are auto-approved.
- One family V2 caught is now missed.
- Recall amounts to 6 of 10 families, with a wide uncertainty interval.
- All evidence is synthetic and comes from a single author.
- The 200-, 100- and 150-case follow-up problem has not been re-measured.

**Production integration: not justified.** On the safety metric the task prioritised (fewer
fraudulent auto-approvals), V3 is worse than V2: 20 against 0. V2's figure is vacuous, because V2
approves nothing at all. Neither engine has been tested on real or independently labelled
dossiers.

**Recommended next steps, in order:**

1. Make an explicit policy decision. Should a campaign that clears V3's checks be approved
   automatically, or only listed as *eligible pending issuer confirmation*? The second option keeps
   V3's workload reduction without approving fabricated dossiers outright.
2. Run frozen V3 once, diagnostically, on the 200-, 100- and 150-case corpora to measure the
   original follow-up problem. This adds evidence without tuning, provided V3 is not changed
   afterwards.
3. Evaluate any further version on an independently authored, double-labelled test set with
   within-family variation, preferably including de-identified real documents
   (`evaluation/final_test_protocol_v2.md` gives the procedure).

## 9. Reproduction

```bash
./.venv/bin/python -B evaluation/verify_candidate_v3_freeze.py                              # freeze check
./.venv/bin/python -m pytest -q tests/test_development_verifier_v3.py tests/test_development_dataset_v3.py tests/test_final_test_v3_protocol.py
./.venv/bin/python -B evaluation/evaluate_development_verifier_v3.py --tag <new-tag>       # development comparison and ablations
```

Do **not** re-run `generate_final_test_v3.py` or `evaluate_final_test_v3.py`. The final test was a
one-time run, and the runner refuses to reuse its output directory.
`evaluation/finalize_final_test_v3.py` rebuilds the report from saved predictions only.
