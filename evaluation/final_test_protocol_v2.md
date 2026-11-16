# Independent final-test protocol for the SevaFund development verifier

This protocol governs the **only** results that may be reported as test performance for a frozen
candidate. Development, validation and diagnostic numbers (including everything in
`docs/development_verifier_v2.md`) are not test results.

## 0. Preconditions

1. The candidate to be tested is frozen: its package hash, configuration digest and runner hash are
   written to a freeze manifest and committed *before* any test case exists. The evaluator refuses to
   run if the hashes differ (`--require-frozen`).
2. Frozen v2.0 (`a054be91…`) has one known defect (foreign-currency amounts read as rupees; see the
   failure analysis). Decide first whether to test v2.0 as-is or a v2.1 that fixes it. A v2.1 must be
   frozen with a new manifest, and its development evidence must come from new tune data, not from
   the consumed v2 validation split.
3. No person who wrote verifier rules or the v2 development corpus authors or labels test cases.

## 1. Test-set construction

- **Authors:** at least two people who have not seen the verifier code, its rule vocabulary, or any
  previous SevaFund corpus. They receive only the campaign categories and the definitions of the
  three labels.
- **Sources (in order of preference):** (a) de-identified real campaign dossiers with known outcomes,
  obtained with consent and processed under a data-protection plan; (b) realistic documents
  re-typeset from public templates (hospital estimates, fee notices, NGO registration certificates)
  with invented details; (c) synthetic narratives. Report the proportion from each source and
  results separately for each.
- **Formats:** real PDFs and scans, including OCR output, multi-page documents, tables without
  column alignment, regional-language headings, and handwritten notes. Include text-snippet-only
  evidence as a separate stratum, because v2 behaves very differently on it.
- **Size and balance:** at least 300 cases, at least 100 per category, with legitimate, fraudulent
  and borderline cases each at least 25% of every category. Precision, recall and FPR intervals at
  this size are roughly ±8–10 points.
- **Novelty:** new scenario families, new institutions and new document sources. Automated checks
  must show no exact or near-duplicate (≥0.8 token Jaccard) story or document against any
  development corpus.
- **Fraud mix:** include fraud that is detectable from the dossier, fraud that is consistent but
  fabricated, and fraud that only an issuer callback could reveal. Record which is which before
  evaluation; do not tell the engine.

## 2. Labelling

- Two independent labellers per case, blind to every engine's output. Each assigns
  `legitimate | fraudulent | borderline`, the *expected action* under the five-decision policy, and,
  for fraud, whether it is *detectable from the dossier*.
- Disagreements are adjudicated by a third reviewer. Report Cohen's κ before adjudication.
- Labels are frozen (hash recorded) before any engine is run.

## 3. Pre-registered metrics and conventions

- Positive class: `fraudulent`. A detection is `FLAG_FOR_REVIEW` or `REJECTED`.
  `NEEDS_MORE_INFORMATION` is **not** a detection; it is reported separately, as is a secondary
  convention that counts it, which must be labelled as such.
- Primary: recall, false-positive rate (legitimate and borderline negatives), fraudulent
  auto-approval rate, and legitimate auto-approval rate, each with a Wilson 95% interval.
- Secondary: precision, F1, manual-review, information-request, rejection and error rates, mean and
  p95 latency, per-category and per-source results, a 3×5 decision matrix, and recall restricted to
  fraud that is detectable from the dossier.
- Workload: expected reviewer-hours per 1,000 campaigns, using a pre-stated minutes-per-action
  assumption.
- Comparators: the baseline heuristic verifier and frozen candidate v1, on identical inputs.
- Paired comparison: McNemar's test on per-case correctness for v2 against each comparator.

## 4. Execution

1. Run every engine exactly once, offline, with Gemini disabled and guarded. Any Gemini-assisted
   configuration is a separate, pre-registered run with its own preflight and quota record, and is
   reported separately.
2. Do not inspect individual test cases until all metrics are computed and written.
3. After results exist, **no change** to any engine, threshold, lexicon or label is allowed. Defects
   found are reported and carried into the next development cycle, which needs a new test set.

## 5. Reporting

Publish the metrics, intervals, decision matrices, every misclassified case with its findings and
redacted audit record, and the label-agreement statistics. Describe the corpus provenance, and state
plainly that results apply to the tested formats and populations, not to real-world fraud
prevalence. Approval remains approval on documentary consistency only unless issuer verification
is in the loop.
