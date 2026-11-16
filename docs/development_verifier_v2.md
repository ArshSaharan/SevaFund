# SevaFund development verifier v2: design, evaluation, and limitations

**Status:** development only. Not wired into any router or production service, and not deployed.
**Frozen candidate:** `sevafund-development-candidate-v2.0`, package hash `a054be91…6fc6`, config
digest `2ac4e448f21d1983` (see `evaluation/development_candidate_v2_freeze.json`).
**Reported run:** `evaluation/runs/development_candidate_v2_all_20261115T205042Z/` (`report.md`,
`results.json`, `predictions.csv`, `explanations.jsonl`).

All numbers below come from offline, deterministic engines on **synthetic** data. Gemini
generation, embeddings and OCR were disabled; a guard aborts the run if any Gemini request is
attempted (0 were made). None of these figures are real-world accuracy, and none describe Gemini
or semantic-RAG performance.

---

## 1. Findings in brief

1. **On its own development corpus, v2 is a large improvement over v1.** Across all 120 cases,
   recall rose from 24.4% to 86.7%, the false-positive rate fell from 28.0% to 5.3%, and the
   fraudulent auto-approval rate fell from 53.3% to 6.7%. Runtime errors fell from 10.0% to 0%.
2. **On the held-out validation split it is weaker, and one defect explains most of the gap.** The
   validation split is six scenario families and 48 cases that were never used for development.
   There, precision is 79.0%, recall 83.3% and the false-positive rate 13.3%. All four validation
   false positives come from a single parsing defect: `GBP 4,000.00` is read as ₹4,000. That rule
   was added late in development and the tune split never exercised it.
3. **The corpus was written by the same author as the verifier.** That shared authorship is the
   main threat to validity. Hand-written documents broke the extractor ten times during
   development, and collapsing table spacing changed 26% of tune-split decisions before the parser
   was fixed. Both show how easily the verifier fits a template.
4. **On older corpora whose evidence is a one-sentence summary rather than a document, v2 approves
   nothing.** It sends 90–96% of cases to NEEDS_MORE_INFORMATION and catches 7.5–25% of fraud. It
   never auto-approves fraud, but at that workload it would not be usable for those inputs.
5. **Recommendation:** do **not** send frozen v2.0 to broader independent testing yet. First make a
   short v2.1 that fixes the currency defect and records an explicit policy for summary-style
   evidence (section 11). Then freeze it and run the protocol in
   `evaluation/final_test_protocol_v2.md` on a newly authored test set.

---

## 2. What was built

The candidate lives in a separate package, `app/services/development_verifier_v2/`. It does not
import from or modify the production verifier, the scoring, the configuration, the schemas or the
routers. The v1 candidate, the baseline verifier, the fraud rules, `rag.py`, `config.py` and
`schemas/ai.py` are byte-identical to the 150-case freeze; `assert_frozen()` still passes.

| Stage | Module | Responsibility |
|---|---|---|
| 1. Document extraction | `engine.load_documents`, `extraction.extract_document` | Resolves uploads inside the upload directory and extracts text with the production `rag.extract_document_text`. Load failures become `load_error` categories rather than exceptions. Detects unreadable documents. |
| 2. Structured evidence normalisation | `extraction`, `money`, `normalize` | Extracts typed fields: person (subject, guardian, payee, staff), organisation and issuer, dates with their roles, rupee amounts with their roles (total, balance, paid, covered), identifiers (UHID, roll, admission, application, registration, PAN, UPI), and treatment, course or work descriptions. Each field records its document, page and RAG-compatible chunk number. Names, organisations, identifiers, dates and amounts are normalised. |
| 3. Evidence consistency | `consistency` | Checks for identity conflicts, identifier conflicts, conflicting cost statements, amount reconciliation against the documented balance, institution mismatches, chronology (discharge before admission, a bill dated before the admission, documents dated after submission, lapsed deadlines, stale costs) and service mismatches. |
| 4. Category-specific verification | `category` | A shared `CategoryProfile` interface with medical, education and community/NGO evidence requirements and concept lexicons. Unmet requirements produce information requests, never fraud findings. |
| 5. Semantic fraud signals | `semantic` | Detects already-settled costs, revoked or cancelled status, third-party payees, off-platform solicitation, documents that are not final, and implausible cost without documents. These use concept combinations within a sentence, with negation and conditional guards, rather than scam keywords. |
| 6. Risk scoring and decision | `decision` | Five decisions with explicit reasons and influencing dimensions, plus descriptive 0–100 scores for five dimensions. |
| 7. Audit logging | `audit` | A pseudonymous record containing reason codes, stage outcomes, finding codes, hashed values and document positions. It contains no names, identifiers, document text, titles or credentials. |

An optional `reasoners=[...]` hook can accept a future Gemini cross-check. None is registered,
none was evaluated, and any failure in a reasoner blocks approval (this is tested).

### Every finding carries provenance

Each `Finding` records:

- the conflicting fields and their extracted values;
- for each value, the document, page and chunk;
- a severity (`material` or `uncertain`) and a confidence;
- a stable code;
- an explanation of why the conflict matters.

Formatting differences are explicitly treated as non-conflicts:

- name order, honorifics, initials, dropped middle names, transliteration (Lakshmi/Laxmi) and
  "Mohd" for Mohammed;
- organisation abbreviations (Govt., Engg., Univ., St.);
- identifier punctuation and zero-padding;
- every common date and rupee style;
- a later-dated revised estimate.

### Agreement is not treated as authenticity

Every decision sets `independent_verification = "UNAVAILABLE"`. Every decision also carries an
uncertainty note saying the documents were checked only against each other. An APPROVED decision
adds that issuer confirmation is recommended before funds are released.

## 3. Why v1 auto-approved fraud

v1 approved a campaign whenever (a) none of its six regex conflict patterns fired and (b) the
retrieved text contained any category keyword. In effect, the *absence of a detected conflict*
meant approval. v1 had:

- no evidence requirements;
- no identity, institution, settlement or payee reasoning;
- no exception guard.

Mutually consistent but fraudulent paperwork therefore passed automatically, which accounts for the
28 frauds approved in the 150-case evaluation. The crash in a currency regex surfaced as an
uncaught exception.

v2 inverts this. Approval requires every category requirement to be **positively satisfied**, with
no finding and no error. Contradictions come from structured fields. Any stage failure yields
VERIFICATION_ERROR, or FLAG_FOR_REVIEW if a material contradiction was already found.

## 4. Decision framework

Rules are evaluated in this order. Scores are descriptive only and are not used as thresholds.

| Decision | Rule |
|---|---|
| `REJECTED` | At least two material findings in **different dimensions**, each with confidence ≥ 0.8. Incomplete documentation can never reach this. |
| `FLAG_FOR_REVIEW` | Any material finding with confidence ≥ 0.6. If a stage also failed, the flag stands and the failure is listed. |
| `VERIFICATION_ERROR` | Any stage, document load or external reasoner failed. The campaign is never approved. |
| `NEEDS_MORE_INFORMATION` | An unmet requirement, an uncertain finding, a material finding below 0.6, or no requirements evaluated. The decision states that missing documents are not evidence of fraud. |
| `APPROVED` | Every requirement is satisfied, with no finding and no error. This is approval on documentary consistency only. |

Every decision records its reasons, the dimensions that influenced it
(identity, financial, institutional, narrative, documentation, or system), the information requests,
and an audit record.

## 5. Currency parsing

**Root cause:** v1's pattern `(?:₹|rs\.?\s*)([\d,]+)` matched the "rs" at the end of a word.
"pape**rs,**" then yielded the empty number `,`, and `int('')` raised. On the v2 corpus, v1 crashed
the same way on "contracto**rs,**" and "bystande**rs,**" (12 cases, all `ValueError`).

**What `money.py` now does:**

- A currency marker must stand alone and cannot sit inside a word.
- The digit-grouping grammar is validated in both Indian (12,34,567) and Western (1,234,567) forms.
- It handles ₹, Rs, Rs., INR, rupee(s), `/-`, decimals, lakh/lac/crore/thousand/k, and amounts
  inside sentences.
- Foreign currency is reported as `FOREIGN_CURRENCY`, never as rupees.
- Malformed values return `valid=False` with an issue code. The parser never raises (fuzz-tested).

The four crashed cases (E150-095 to E150-098) now parse without error. These are crash regressions
only: their decisions are not asserted and nothing was tuned on them.

## 6. Development dataset (`evaluation/development_scenarios_v2.jsonl`)

**Size and composition:** 120 synthetic cases; 45 legitimate, 45 fraudulent and 30 borderline;
40 per category.

**Families and split:**

- 15 scenario families, 5 per category, each with its own institutions, document sources, layouts
  and vocabulary.
- Families are assigned **whole** to a tune split (9 families, 72 cases) or a validation split
  (6 families, 48 cases).
- No family or document source crosses the split (this is tested).

**Documents:** 1–3 realistic documents per case: letterheads, forms, tables, dotted leaders,
multi-page cost sheets, emails, minutes and registration certificates. Amounts, dates and names use
different styles in different places.

**Variants** (each family yields 3 legitimate, 3 fraudulent and 2 borderline cases):

- **Legitimate:** clean; harmless formatting differences; partially paid; partial goal; high but
  documented cost; superseded estimate; required document missing.
- **Fraudulent:** wrong identity, already settled, inflated amount, impossible chronology,
  identifier conflict, wrong institution, payment diversion, different service, revoked
  eligibility, two combined contradictions, consistent but fabricated (3 cases), and thin evidence
  (3 cases).
- **Borderline:** no documents, provisional or draft documents, modest unexplained excess, partial
  name match.

**Fraud a dossier-only verifier cannot establish (deliberate):** six of the 45 fraud cases
(`detectable_from_dossier: false`). They keep recall honest. The best attainable is about 39 flags
plus three information requests.

**Labels:** assigned by the author together with a written `adjudication_note` and
`expected_action`. They are not independently adjudicated.

**Leakage controls and their limits:**

- No family crosses the split.
- No story repeats an earlier corpus and no template boilerplate is shared with one (tested).
- The generator is deterministic and the corpus is regenerated in a test.
- The existing 200-, 100-, 150- and 120-case corpora are hash-checked as unchanged.
- **The limit:** one author wrote the generator, the validation templates and the verifier. Four
  validation cases (DV2-028, DV2-037, DV2-069, DV2-105) were printed while checking the generator,
  before any verifier code existed. The validation split is therefore a family-held-out
  development check, not an independent test.

## 7. Evaluation conventions

- Positive class: `fraudulent`; legitimate and borderline cases are negatives.
- A **fraud detection** is `FLAG_FOR_REVIEW` or `REJECTED`. For the two legacy engines, an emitted
  red flag also counts, because production routes it to FLAGGED.
- `NEEDS_MORE_INFORMATION` is **never** counted as a detection in primary metrics. A secondary
  convention that does count it is reported separately and labelled as such.
- The engines saw identical cases and identical uploads:
  - **baseline:** existing fallback verifier with lexical retrieval;
  - **v1:** its frozen protocol of the top 5 lexically retrieved chunks; retrieval dropped no
    document in any case;
  - **v2:** every upload extracted in full.
- Latency is end-to-end local processing. For v2 it includes file loading and extraction.
- Intervals are Wilson 95% intervals.

## 8. Results (frozen v2.0, all 120 cases)

### Original vs improved

| Metric | Baseline heuristics | Candidate v1 (original) | Candidate v2 (improved) |
|---|---:|---:|---:|
| Precision | 34.2% (21.2–50.1) | 34.4% (20.4–51.7) | 90.7% (78.4–96.3) |
| Recall | 28.9% (17.7–43.4) | 24.4% (14.2–38.7) | 86.7% (73.8–93.7) |
| F1-score | 31.3% | 28.6% | 88.6% |
| False-positive rate | 33.3% (23.7–44.6) | 28.0% (19.1–39.0) | 5.3% (2.1–12.9) |
| Fraudulent auto-approval rate | 71.1% | 53.3% | 6.7% |
| Legitimate auto-approval rate | 71.1% | 51.1% | 86.7% |
| Manual-review rate (FLAG_FOR_REVIEW) | 31.7% | 25.8% | 34.2% |
| Needs-more-information rate | 0.0% | 16.7% | 29.2% |
| Rejection rate | 0.0% | 0.0% | 1.7% |
| Runtime error rate | 0.0% | 10.0% | 0.0% |
| Mean latency (ms) | 0.60 | 0.46 | 5.64 |

**Confusion matrices (TP / FP / FN / TN):**

- baseline: 13 / 25 / 32 / 50
- v1: 11 / 21 / 34 / 54
- v2: 39 / 4 / 6 / 71

**v2 decisions by ground truth:**

| Label | APPROVED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | REJECTED | VERIFICATION_ERROR |
|---|---:|---:|---:|---:|---:|
| legitimate (45) | 39 | 3 | 3 | 0 | 0 |
| fraudulent (45) | 3 | 3 | 37 | 2 | 0 |
| borderline (30) | 0 | 29 | 1 | 0 | 0 |

The two rejections (DV2-028 and DV2-108) are both fraud cases with two independent planted
contradictions.

**Workload.** 65.0% of cases were not auto-approved. That figure is driven by this corpus, which is
62.5% fraudulent or borderline. It says nothing about the workload at a realistic fraud prevalence.

### Tune split vs held-out validation split (v2)

| Split | Precision | Recall (95% CI) | FPR (95% CI) | Fraud auto-approved | Legit approved | TP/FP/FN/TN |
|---|---:|---:|---:|---:|---:|---|
| tune (9 families, 72) | 100.0% | 88.9% (71.9–96.2) | 0.0% (0.0–7.9) | 7.4% | 96.3% | 24/0/3/45 |
| validation (6 families, 48) | 79.0% | 83.3% (60.8–94.2) | 13.3% (5.3–29.7) | 5.6% | 72.2% | 15/4/3/26 |

On the validation split, baseline and v1 reach recall of 44.4% and 44.4%, false-positive rates of
40.0% and 50.0%, and fraud auto-approval of 55.6% and 33.3%.

### Category-wise

| Category | Engine | Precision | Recall | FPR | Fraud auto-approved | Legit approved | TP/FP/FN/TN |
|---|---|---:|---:|---:|---:|---:|---|
| Medical | baseline | 16.7% | 6.7% | 20.0% | 93.3% | 86.7% | 1/5/14/20 |
| Medical | v1 | 25.0% | 6.7% | 12.0% | 73.3% | 73.3% | 1/3/14/22 |
| Medical | **v2** | 100.0% | 86.7% | 0.0% | 6.7% | 93.3% | 13/0/2/25 |
| Education | baseline | 25.0% | 6.7% | 12.0% | 93.3% | 93.3% | 1/3/14/22 |
| Education | v1 | 30.8% | 26.7% | 36.0% | 53.3% | 46.7% | 4/9/11/16 |
| Education | **v2** | 76.5% | 86.7% | 16.0% | 6.7% | 73.3% | 13/4/2/21 |
| Community | baseline | 39.3% | 73.3% | 68.0% | 26.7% | 33.3% | 11/17/4/8 |
| Community | v1 | 40.0% | 40.0% | 36.0% | 33.3% | 33.3% | 6/9/9/16 |
| Community | **v2** | 100.0% | 86.7% | 0.0% | 6.7% | 93.3% | 13/0/2/25 |

Education recall, which was 0% for v1 on the 150-case benchmark, is 86.7% here. All of v2's
education false positives come from the foreign-currency defect.

### Ablation

| Configuration | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit approved |
|---|---:|---:|---:|---:|---:|---:|
| full v2 | 90.7% | 86.7% | 88.6% | 5.3% | 6.7% | 86.7% |
| without cross-document consistency | 100.0% | 31.1% | 47.5% | 0.0% | 60.0% | 93.3% |
| without semantic signals | 88.2% | 66.7% | 75.9% | 5.3% | 26.7% | 86.7% |
| without category awareness | 90.2% | 82.2% | 86.1% | 5.3% | 6.7% | 82.2% |
| requirements only (no consistency, no semantic) | n/a | 0.0% | 0.0% | 0.0% | 91.1% | 93.3% |

- **Cross-document consistency is the main source of detection.** Without it, recall falls to
  31.1%, and the fraud auto-approval rate rises from 6.7% to 60.0%.
- **Semantic signals contribute settlement, eligibility and payment-routing detection.**
- **Category awareness adds little measurable value on this corpus.** It adds 4.4 points of recall
  and 4.4 points of legitimate approval (2 of 45 cases each), mostly through the concept lexicon used for service
  matching. Because category-specific requirements mostly coincide with generic cost-evidence
  checks here, this ablation does not test them well.
- **Evidence requirements on their own detect nothing.** Consistent paperwork passes, which is the
  failure mode v1 had.

### Document-consistency detection (planted contradiction found as a material finding)

| Planted kind | Cases | v2 full | − cross-document | − semantic | − category |
|---|---:|---:|---:|---:|---:|
| amount | 6 | 100% | 0% | 100% | 100% |
| chronology | 4 | 100% | 0% | 100% | 100% |
| eligibility | 4 | 100% | 100% | 0% | 100% |
| identifier | 5 | 100% | 0% | 100% | 100% |
| identity | 4 | 100% | 0% | 100% | 100% |
| institution | 4 | 100% | 0% | 100% | 100% |
| payment routing | 5 | 100% | 100% | 0% | 100% |
| service | 3 | 100% | 0% | 100% | 33.3% |
| settlement | 6 | 100% | 100% | 33.3% | 100% |

- Spurious material findings occurred on 3 of 45 legitimate cases and 1 of 30 borderline cases.
  All four are the foreign-currency defect.
- Each planted contradiction was written by the same author as its detector, and the 100% figures
  should be read in that light.

### Robustness to formatting-only perturbations

Decision agreement was 100% under each of the four perturbations, applied to all 120 cases:

- currency style;
- date style;
- name order and case;
- collapsed table spacing, as in OCR output.

Two caveats apply:

- Collapsed table spacing was used during development on the tune split. Only the validation-split
  figure for that perturbation is held out.
- The first two frozen runs reported 96.7% currency agreement. That was caused by a defect in the
  perturbation *tool*, which changed amounts. The tool was fixed and is now guarded by a test; the
  verifier was not touched. Those two runs are marked `SUPERSEDED.md`.

## 9. Failure analysis

**A. Foreign-currency amount read as rupees.** *Validation; 3 legitimate and 1 borderline flagged.*

- **Cases:** DV2-065, -066, -067 and -072 (overseas master's deposit).
- **What happens:** the bare-amount row rule reads `Deposit due: GBP 4,000.00` as a ₹4,000 balance.
  `AMOUNT_EXCEEDS_BALANCE` then fires at confidence 0.75.
- **Origin:** the rule was added to make table extraction independent of column spacing. It never
  checks the currency token before the number, and the tune split had no foreign currency.
- **Status:** a real, deterministic defect. It accounts for every false positive v2 produced and is
  left unfixed because the candidate is frozen.

**B. Consistent but fabricated dossiers approved.** *3 fraud cases: DV2-022, DV2-078, DV2-102.*

These dossiers are correct by construction: nothing in them contradicts anything else. Only issuer
verification, an independent registry, or cross-campaign duplicate detection can catch them. They
mark the limit of any dossier-only verifier, and this is why approval is labelled as documentary
consistency only.

**C. Fraud with thin evidence sent to information request.** *3 cases: DV2-030, DV2-062, DV2-118.*

An unattributable typed note doesn't satisfy the cost-evidence requirement, so v2 asks for proper
documents rather than accusing. That is the intended behaviour, but it is not a fraud detection and
is counted as a miss.

**D. Legitimate cases missing a required document.** *3 cases.*

These are sent to an information request as designed. They are the 3 legitimate NEEDS_MORE_INFORMATION
decisions.

**E. Errors found during development and fixed before the freeze.** These show how much the
extractor depended on templates:

- Ten hand-written test documents failed on first contact. The causes were: zero-padded IDs,
  transliterated names, organisation names made only of generic words, "Sangha", fee notices not
  recognised as cost documents, vendor names, a service phrase running into a table, and garbage
  text treated as readable.
- Collapsing table spacing changed 19 of 72 tune decisions. One of those changes was unsafe: an
  identity-mismatch case became APPROVED.

Every fix was general (grammar, vocabulary, normalisation); none was keyed to a case.

**F. Evidence written as a one-sentence summary rather than a document.** *Older corpora; one run
of frozen v2, no changes made afterwards.*

| Corpus | Precision | Recall | FPR | Fraud auto-approved | Legit approved | Needs more info |
|---|---:|---:|---:|---:|---:|---:|
| independent 150 | 100.0% | 16.7% | 0.0% | 0.0% | 0.0% | 93.3% |
| independent 100 | 75.0% | 7.5% | 1.7% | 0.0% | 0.0% | 96.0% |
| fundraising 200 | 100.0% | 25.0% | 0.0% | 0.0% | 0.0% | 90.0% |

On the 150-case set, v1 had recall of 26.7%, fraud auto-approval of 46.7% and legitimate approval of
63.3%.

These corpora's "documents" are single sentences with no issuer, date or reference, such as:

> The rehabilitation calendar lists six supervised visits… Applicant: Aarav Menon. Amount
> requested: ₹74,500.

- **Unmet requirements:** cost evidence was unmet in 138 of the 140 information requests on the
  150-case set, so v2 approves nothing.
- **Missed contradictions:** its structured checks rarely fire on contradictions expressed in prose,
  such as "the same six sessions were reimbursed to the travel coordinator last month".

Whether requiring an attributable document is the right policy depends on what real uploads look
like. This is the clearest evidence that v2's performance is tied to document format.
Source: `evaluation/runs/diagnostic_v2_prior_benchmarks_20261115T205120Z/results.json`.

## 10. Remaining limitations

1. **Single-author synthetic data.** Corpus, labels, planted contradictions and detectors share one
   author. No human-reviewed or real labels exist yet.
2. **Template sensitivity.** Extraction is rule-based. It handled the formats it was developed on,
   formats added during development, and the perturbations above. Unseen layouts, regional
   languages, handwriting and noisy OCR are untested.
3. **Prose contradictions are mostly missed.** Settlement, eligibility and routing detection
   recognise administrative phrasing, not arbitrary narrative.
4. **Dossier-only verification is blind** to consistent fabrication, to reused documents across
   campaigns, and to collusion with an issuer. Issuer callbacks or registry lookups (for example
   NGO Darpan, or hospital and university verification) would be needed.
5. **Lexicon coverage.** Service matching relies on hand-built concept groups. A service domain
   outside the lexicon falls back to "uncertain" (an information request), never to a flag.
6. **Foreign-currency defect** (failure A). Several other inputs are also unhandled:
   - amounts written in words ("rupees fifty thousand");
   - multiple currencies within one document;
   - pet names standing in for registered given names (tested as a known limitation).
7. **Small samples.** Validation has 48 cases. Its 95% intervals span 61–94% for recall and
   5–30% for the false-positive rate.
8. **Workload and cost** were not measured at realistic prevalence. Latency covers local processing
   only and excludes OCR, network calls and human review.
9. **The audit hash is unsalted.** It is pseudonymous rather than anonymous; production would need
   an HMAC with a managed secret.
10. **IND-064 and IND-070 are routed to NEEDS_MORE_INFORMATION, not flagged.** Their documents
    contain no cost evidence, and v2 has no duration-conflict check (claimed twelve months against
    a documented ten weeks).
11. **No Gemini component was built or evaluated.** The reasoner hook is untested with a real model.

## 11. Recommendation

Frozen v2.0 is **not yet ready** for broader independent testing. It is close: a short v2.1 cycle
should:

1. **Fix failure A.** Reject any bare-amount row whose label carries a foreign-currency token, and
   add a regression test that mixes GBP, USD and INR.
2. **Decide the evidence policy for summary-style uploads.** One option is a lower evidence tier
   that routes to a quick human check instead of a full information request. Then measure the
   resulting workload.
3. **Optionally add a duration-conflict check.**

After that cycle, freeze v2.1 with a new manifest. Collect new tune data for any further changes;
the v2 validation split is now consumed. Then run `evaluation/final_test_protocol_v2.md`, which
calls for independently authored, double-labelled cases, preferably including de-identified real
dossiers and real PDFs or OCR. Production replacement should be considered only after that test,
and only alongside an issuer-verification step.

## 12. Reproducing everything

Run from the repository root. No API key is needed, and no paid call is made.

```bash
# Tests: parsing, contradictions, missing evidence, failures, audit privacy, dataset integrity
.venv/bin/python -m pytest tests/test_development_verifier_v2.py tests/test_development_dataset_v2.py -q

# Optional: regenerate the development corpus (deterministic; a test checks it is byte-identical)
.venv/bin/python evaluation/generate_development_dataset_v2.py

# Paired comparison (baseline vs v1 vs v2 + ablations + robustness); refuses to run if v2 changed
.venv/bin/python evaluation/evaluate_development_candidate_v2.py --split all --require-frozen

# One-shot diagnostic of frozen v2 on the older corpora (reads them, never writes)
.venv/bin/python evaluation/diagnose_v2_on_prior_benchmarks.py
```

Each run writes a new directory under `evaluation/runs/`. Its contents are:

- `report.md`: tables generated directly from the results, so nothing is transcribed by hand;
- `results.json`;
- `predictions.csv`: per-case decisions for every engine and ablation;
- `explanations.jsonl`: per-case reasons, findings with document, page and chunk, unmet
  requirements, information requests and audit stages;
- `run_config.json`: hashes, config and Python version.

Use `--split tune` or `--split validation` for a single split.

## 13. Files

| Path | Purpose |
|---|---|
| `app/services/development_verifier_v2/` | Candidate: `schemas`, `money`, `normalize`, `extraction`, `consistency`, `category`, `semantic`, `decision`, `audit`, `engine`, `config` |
| `tests/test_development_verifier_v2.py` | 100 behaviour and regression tests (parametrised cases counted individually) |
| `tests/test_development_dataset_v2.py` | Dataset integrity, frozen-corpus hashes, perturbation validity, metric conventions |
| `evaluation/generate_development_dataset_v2.py`, `development_scenarios_v2.jsonl` | Development corpus |
| `evaluation/evaluate_development_candidate_v2.py`, `evaluation/perturbations.py` | Evaluation runner and robustness perturbations |
| `evaluation/diagnose_v2_on_prior_benchmarks.py` | Out-of-distribution diagnostic |
| `evaluation/development_candidate_v2_freeze.json` | Freeze manifest, development-exposure statement and post-freeze changes |
| `evaluation/final_test_protocol_v2.md` | Independent final-test protocol |
