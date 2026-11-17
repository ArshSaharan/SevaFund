# Failure analysis: independent 100-case SevaFund benchmark

## Scope

This diagnostic uses the saved offline predictions, both synthetic datasets, and the current verifier/retrieval source. No benchmark data, production scoring code, or thresholds were changed. Results are from Python heuristics plus lexical retrieval; Gemini generation and embedding were disabled.

## Root-cause summary

The new benchmark produced TP=38, FP=57, FN=2, TN=3; precision 40.0%, recall 95.0%, F1 56.3%, and FPR 95.0%. All 57 false positives and all 38 true positives were `FLAG_FOR_REVIEW`. There were no `REJECT` or `NEEDS_MORE_INFO` outcomes and no red-flag regex matches.

| Failure area | Evidence in this run | Root cause | Recommended improvement (not applied) |
|---|---|---|---|
| 39 legitimate campaigns sent to review | Specificity <50 in 37/39; no retrieved document in 14/39; 12 cases had both. Remaining 25 had low specificity only; two had missing evidence only. Cost penalties: 0. | The score is conservative for varied, unusual, and non-medical narratives. Location, institution, clinician, and document-reference patterns dominate specificity. A missing document sets documentation to 25; retrieved-document presence sets it to 80. | Treat “needs evidence” separately from fraud risk. Review the specificity features against legitimate atypical cases on a development set; measure review burden and fraud capture separately. Do not tune the held-out benchmark. |
| Cost/benchmark effects on legitimate false positives | 30/39 had an in-range benchmark; 9 had no matching benchmark and received the default plausibility score 85. None had an elevated or excessive benchmark status. | Excessive-cost rules did not cause these false positives. The larger causes were narrow specificity matches and missing-document credit. | Expand benchmark coverage and uncertainty handling using separately collected development data; do not infer fraud solely from an unmodeled but plausible expense. |
| `IND-064` auto-approved | Score 87.3; plausibility 92, specificity 75, red-flag score 100, documentation 80. The ₹39,400 goal falls within the education tuition benchmark. The retrieved receipt states the book set was delivered, contradicting a second-payment request. | Offline heuristic scoring sees one retrieved document and awards documentation credit; it does not compare the receipt’s facts with the campaign claim. | Add a separately validated claim/evidence consistency component and make contradictions reduce confidence or trigger review; keep evidence presence distinct from evidence support. |
| `IND-070` auto-approved | Score 83.6; plausibility 92, specificity 60, red-flag score 100, documentation 80. The ₹77,500 goal falls within the tuition benchmark. The claim budgets a year while the retrieved course calendar covers ten weeks. | Same presence-versus-consistency failure: the semantic conflict is available in the retrieved text but absent from local authenticity scoring. | Test time-period, quantity, identity, amount, and reimbursement reconciliation as explicit evidence checks on development examples before any independent retest. |
| No rejections | Minimum score across the new set is 61.2. All cases are above the 50 review threshold; none reaches the `<35` rejection region. | The rejection branch is score-gated and receives no red-flag penalty in this corpus. The new narratives intentionally avoid existing red-flag regex phrases. | Add hard-negative and subtle-fraud development cases, then evaluate rejection calibration separately. Do not lower the rejection threshold based on this holdout. |

### Legitimate false-positive dimensions

The 39 legitimate flags all had red-flag scores of 100 and final scores from 63.0 to 79.8, so the 80 auto-approval threshold was not reached. Plausibility was 92 in 30 cases and the default 85 in nine; no legitimate false positive received an elevated-cost penalty. Specificity was below 50 in 37 cases. Fourteen lacked retrieved evidence and therefore received a documentation score of 25; the other 25 had one retrieved document and a documentation score of 80. The two missing-document-only cases had specificity at least 50.

These causes overlap. Of the 39 cases, 25 had low specificity only, 12 had both low specificity and no retrieved document, and two had no retrieved document without low specificity. This accounts for all 39; cost penalties and other independent causes contributed zero.

The current score weights are plausibility 30%, specificity 25%, red-flag score 25%, and documentation 20%. The decision thresholds are `AUTO_APPROVE` at 80 or above, `FLAG_FOR_REVIEW` at 50 through 79.9, `NEEDS_MORE_INFO` at 35 through 49.9, and `REJECT` below 35. These are unchanged.

## Were retrieved documents used in scoring?

Retrieval did occur. The new benchmark has 84 attached-document cases, and lexical retrieval returned evidence for all 84: 26 legitimate, 40 fraudulent, and 18 borderline cases. The two false negatives both had one retrieved chunk.

In the offline fallback path, retrieved evidence is attached to the result for display, but its text is not passed into the local score calculation. The verifier passes only the number of distinct retrieved file URLs into `_verify_with_local_heuristics`. One document yields a documentation score of 80 (16 composite points); no retrieved document yields 25 (5 composite points). Thus retrieval affects the score through document count, not whether the document corroborates the campaign. By contrast, the Gemini path places evidence excerpts in the generation prompt, but that path was not evaluated here.

## Why `REJECT` never occurred

The code only assigns `REJECT` below 35; scores from 35 to below 50 become `NEEDS_MORE_INFO`, and 50–79.9 become `FLAG_FOR_REVIEW`. The lowest new-benchmark score is 61.2, and no campaign matched a red-flag pattern, so no score entered either lower band. Zero rejections therefore means this dataset did not exercise that branch; it does not show the rejection behavior is calibrated.

## Original 200-case set versus the new 100-case set

| Measure | Original 200 | New 100 | Shift |
|---|---:|---:|---|
| Medical / education / community | 150 / 29 / 21 (75% / 14.5% / 10.5%) | 50 / 25 / 25 (50% / 25% / 25%) | More non-medical examples in the new set |
| Cases with retrieved documents: legitimate | 80/80 | 26/40 | New set includes legitimate cases without documents |
| Cases with retrieved documents: fraudulent | 12/80 | 40/40 | New set emphasizes contradictory evidence |
| Cases with retrieved documents: borderline | 10/40 | 18/20 | More ambiguous evidence in the new set |
| Fraud cases matching existing red-flag regexes | 66/80 | 0/40 | New fraud cases are subtler and avoid literal rule phrases |
| Precision / recall / F1 / FPR | 76.2% / 100.0% / 86.5% / 20.8% | 40.0% / 95.0% / 56.3% / 95.0% | Lower precision and much higher review burden on the new set |

The original generator reused three legitimate-medical narrative forms, six medical-fraud patterns repeated ten times, eight borderline templates repeated five times, and five templates for each education/social class. Its fraud descriptions often directly matched the existing red-flag patterns. The new corpus has no exact old story duplicates, no shared five-word story shingles (maximum Jaccard 0.0000), and no matches against the existing red-flag patterns in stories or document text. The old result was therefore strongly dependent on overt phrase patterns and a medical-heavy mix. The new result exposes category and evidence-use weaknesses that the old distribution did not.

## Root-cause tracing in source

- `app/services/ai_verifier.py`: retrieves and formats evidence, then sends only retrieved-document count to the local heuristic. The Gemini path separately constructs prompt evidence text.
- `app/services/ai_verifier.py`: computes the four weighted dimensions and applies the review/approval/rejection bands.
- `app/services/fraud_detector.py`: uses a finite keyword table for cost benchmarks and explicit regexes for red flags and specificity.
- `app/services/rag.py`: extracts/chunks documents and ranks them by lexical overlap when embeddings are disabled. Retrieval relevance is not a semantic consistency judgment.

## Holdout-safe development and testing procedure

1. Freeze and hash this 100-case benchmark, its labels, and the current result. Do not use its case-level errors to tune prompts, rules, weights, or thresholds. This diagnostic has now exposed the cases, so treat the benchmark as consumed for future development decisions.
2. Create a separate development corpus with independently authored cases, document-consistency labels, and adjudicated outcomes. Split by scenario family and source so near-duplicate narratives or documents cannot cross train/dev/test partitions.
3. Make one documented change at a time and evaluate only on development data. Track `AUTO_APPROVE`, `FLAG_FOR_REVIEW`, `NEEDS_MORE_INFO`, and `REJECT` separately; report fraud recall, false-positive/review rate, and document contradiction performance.
4. Freeze code, model/prompt, thresholds, and run configuration before a new independent evaluation. Record hashes and evaluation protocol before unsealing labels.
5. Have reviewers blinded to system outputs adjudicate a fresh, separately sourced holdout. Run it once for the stated comparison. If a change follows, retire that holdout from confirmatory use and collect another.
6. Keep a dedicated evidence-consistency test suite in development data for amounts, identities, dates, quantities, reimbursement credits, and scope differences. Retrieval success alone must not be treated as proof that evidence supports a claim.

## Provenance

- New benchmark SHA-256: `fc1188c2851342683a096f4235534d9d98deb3f390bd9840feb8b13b9a07aa46`.
- Original benchmark SHA-256: `cb6d08c426d8ecbfce9c661d9ef32d756ab68a052671c3fadad31d43b1cd3099`.
- New result and case predictions remain in `independent_benchmark_100_offline_20261115T153504Z/`; neither benchmark dataset was edited.
