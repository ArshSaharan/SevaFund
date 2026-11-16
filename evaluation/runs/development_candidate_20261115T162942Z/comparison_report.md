# SevaFund development-only verifier comparison

## Scope and reproducibility

This run evaluates 120 **synthetic** scenarios created for development. It is offline Python plus lexical retrieval: Gemini generation and embedding calls were disabled and the run made zero Gemini API requests. The production verifier, scoring thresholds, deployment settings, both prior datasets, and previous evaluation artifacts were left untouched by this implementation.

The corpus contains 48 legitimate, 48 fraudulent, and 24 borderline cases. Twelve scenario families each contain 4/4/2 cases and one document-source group; four families per category are held together in each of three group folds. Dataset SHA-256: `6eb46685656dd7ceaeea6971451738a6fd2a841ca2f0d2a5e02301eb7db7eb88`. Full predictions, grouped metrics, and reproducibility hashes are in `results.json`, `predictions.csv`, `baseline.json`, `candidate.json`, and `run_config.json`.

Reproduce from the repository root with:

```sh
PYTHONPATH=. .venv/bin/python evaluation/evaluate_development_candidate.py
```

The runner force-disables Gemini, compares identical case IDs and labels, builds identical baseline/candidate retrieval queries, and checks retrieved-document counts match case by case. Latency for both systems covers retrieval plus verifier decision processing.

## Paired results

Fraudulent is the positive class. Legitimate and borderline cases are negative for binary metrics. A case counts as flagged when it is recommended for `FLAG_FOR_REVIEW` or `REJECT`, or has an explicit red flag. Review burden counts `FLAG_FOR_REVIEW`, `NEEDS_MORE_INFO`, and `REJECT`.

| Offline configuration | Precision | Recall | F1 | False-positive rate | Review burden | Mean end-to-end latency |
|---|---:|---:|---:|---:|---:|---:|
| Existing Python heuristics + lexical retrieval | 34.04% | 66.67% | 45.07% | 86.11% | 94/120 (78.33%) | 0.34 ms |
| Development candidate + lexical retrieval | 100.00% | 100.00% | 100.00% | 0.00% | 72/120 (60.00%) | 0.17 ms |

| Configuration | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| Existing baseline | 32 | 62 | 16 | 10 |
| Development candidate | 48 | 0 | 0 | 72 |

The candidate sent all 48 fraudulent cases to manual review, requested more information for all 24 borderline cases, approved all 48 legitimate cases, and rejected none. It produced the same binary result in each 40-case category and each family-held-out fold. Detailed class, category, family, source, and fold breakdowns are in `results.json`.

## Candidate architecture

- `app/services/development_verifier.py` is separate from production requests. It checks retrieved evidence for explicit amount, beneficiary/payee, duration, quantity, reimbursement/prior-delivery, and authorized-purpose conflicts, and classifies evidence as supporting, contradictory, incomplete, or unavailable.
- Category relevance is checked before approval: medical records need care context, education records need student/course/institution context, and community records need project/community context. Category mismatch and missing/preliminary proof request more information.
- Consistent campaign-specific evidence can be approved; contradictions route to manual review; missing/incomplete evidence requests more information. Rejection requires multiple independent conflicts plus an explicit document-fabrication indicator. No case in this corpus meets that corroboration rule, so zero rejections is expected.
- `evaluation/generate_development_dataset.py` creates the development set. `evaluation/evaluate_development_candidate.py` runs the existing baseline and candidate offline, producing paired predictions, hashes, action metrics, grouped summaries, and configuration.
- `IND-064` and `IND-070` appear only in the requested regression tests; they are excluded from the dataset and metrics. Both route to review rather than approval or rejection.

## Interpretation and limits

The observed improvement is supported only for this constructed synthetic development corpus. Fraud labels are deliberately paired with generated document contradictions, legitimate documents repeat claim fields consistently, and borderline documents explicitly state that details are pending. This makes the task unusually separable and likely inflates the perfect scores. The narratives share a generated structure inside each family. Keeping families and document sources within folds prevents cross-fold family leakage, but does not make this an independently authored final test set.

This candidate is deterministic rules over lexical retrieval. The result does not establish semantic retrieval quality, Gemini RAG performance, real-world fraud accuracy, risk calibration, or production readiness. The sub-millisecond latency covers local retrieval and decision processing only; it excludes network, uploads, OCR, and human review. A zero FPR on 72 synthetic non-fraud cases is not evidence of low real-world FPR.

The candidate was not tuned against either previous benchmark. The two previous IDs were used only for fixed regression checks. A missed purpose conflict in development was caught by a new unit test and fixed; the final run also aligns retrieval query construction and measures latency consistently.

## Recommended next evaluation

Freeze the candidate and have independent reviewers author and adjudicate a new untouched test set using realistic, de-identified cases. Split by beneficiary, institution, document source, and time to prevent correlated examples from crossing partitions. Include ambiguous requests and legitimate unusual expenses, blind reviewers to model outcomes, pre-register label/action mappings and metrics, and report confidence intervals and workload by category. Test Gemini generation/embeddings separately only after explicit authorization and endpoint/quota preflight. Do not change production based on this development result alone.
