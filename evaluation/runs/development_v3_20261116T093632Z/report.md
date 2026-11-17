# SevaFund V3 paired development evaluation

Synthetic development data only. No Gemini calls, embeddings, semantic RAG, or external issuer verification were used.
Primary binary classification metrics exclude borderline cases; borderline outcomes are reported separately.

## V2 versus V3

| Engine | N | Precision | Recall | F1 | FPR (legitimate) | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Reject | Runtime errors | Mean / p50 / p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2_original | 180 | 73.9% | 56.7% | 64.2% | 20.0% | 0 (0.0%) | 0 (0.0%) | 26.7% | 70.0% | 3.3% | 0.0% | 2.28 / 1.84 / 3.95 |
| V3_full | 180 | 83.3% | 100.0% | 90.9% | 20.0% | 0 (0.0%) | 24 (40.0%) | 41.1% | 42.2% | 3.3% | 0.0% | 2.32 / 1.85 / 4.15 |

### V2_original confusion matrices

Binary fraud-versus-legitimate (borderline excluded):

| | Predicted fraud/review | Predicted approved |
|---|---:|---:|
| Actual fraudulent | 34 | 26 |
| Actual legitimate | 12 | 48 |

Three-class disposition matrix:

| Actual \ Predicted | Approved | Flag/reject | Needs info/error |
|---|---:|---:|---:|
| legitimate | 0 | 12 | 48 |
| fraudulent | 0 | 34 | 26 |
| borderline | 0 | 8 | 52 |

Category-wise adjudicable metrics:

| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| COMMUNITY | 60 | 75.0% | 60.0% | 66.7% | 20.0% | 26.7% | 70.0% |
| EDUCATION | 60 | 33.3% | 10.0% | 15.4% | 20.0% | 13.3% | 86.7% |
| MEDICAL | 60 | 83.3% | 100.0% | 90.9% | 20.0% | 40.0% | 53.3% |

Grouped validation split (families held out from development split):

| Split | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 90 | 66.7% | 40.0% | 50.0% | 20.0% | 24.4% | 73.3% |
| validation | 90 | 78.6% | 73.3% | 75.9% | 20.0% | 28.9% | 66.7% |

Borderline outcomes: APPROVED: 0, NEEDS_MORE_INFORMATION: 52, FLAG_FOR_REVIEW: 8, REJECTED: 0, VERIFICATION_ERROR: 0.

### V3_full confusion matrices

Binary fraud-versus-legitimate (borderline excluded):

| | Predicted fraud/review | Predicted approved |
|---|---:|---:|
| Actual fraudulent | 60 | 0 |
| Actual legitimate | 12 | 48 |

Three-class disposition matrix:

| Actual \ Predicted | Approved | Flag/reject | Needs info/error |
|---|---:|---:|---:|
| legitimate | 24 | 12 | 24 |
| fraudulent | 0 | 60 | 0 |
| borderline | 0 | 8 | 52 |

Category-wise adjudicable metrics:

| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| COMMUNITY | 60 | 83.3% | 100.0% | 90.9% | 20.0% | 40.0% | 56.7% |
| EDUCATION | 60 | 83.3% | 100.0% | 90.9% | 20.0% | 43.3% | 43.3% |
| MEDICAL | 60 | 83.3% | 100.0% | 90.9% | 20.0% | 40.0% | 26.7% |

Grouped validation split (families held out from development split):

| Split | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 90 | 83.3% | 100.0% | 90.9% | 20.0% | 44.4% | 44.4% |
| validation | 90 | 83.3% | 100.0% | 90.9% | 20.0% | 37.8% | 40.0% |

Borderline outcomes: APPROVED: 0, NEEDS_MORE_INFORMATION: 52, FLAG_FOR_REVIEW: 8, REJECTED: 0, VERIFICATION_ERROR: 0.

## V3 ablations

Each variant uses the same 180 cases. These are component contribution measurements, not independent test results.

| Variant | Precision | Recall | F1 | FPR | Fraud auto-approved | Manual review | Info request | Reject | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_v3 | 83.3% | 100.0% | 90.9% | 20.0% | 0 | 41.1% | 42.2% | 3.3% | 0.0% |
| without_category_awareness | 83.3% | 100.0% | 90.9% | 20.0% | 0 | 41.1% | 37.2% | 3.3% | 0.0% |
| without_cross_document_checks | 100.0% | 33.3% | 50.0% | 0.0% | 0 | 11.1% | 73.9% | 0.0% | 0.0% |
| without_improved_financial_parsing | 83.3% | 100.0% | 90.9% | 20.0% | 0 | 41.1% | 55.6% | 3.3% | 0.0% |
| without_tiered_evidence_requirements | 83.3% | 100.0% | 90.9% | 20.0% | 0 | 41.1% | 55.6% | 3.3% | 0.0% |
| without_uncertainty_policy | 83.3% | 100.0% | 90.9% | 20.0% | 0 | 41.1% | 55.6% | 3.3% | 0.0% |

## Method and limits

- Both versions receive the same case IDs, labels, structured campaign fields, and document text. V2 does not receive V3-only goal-currency metadata.
- Fraud precision/recall/F1/FPR use the 120 legitimate/fraudulent scenarios; borderline cases are excluded from binary metrics and shown in the 3-class disposition matrix.
- `FLAG_FOR_REVIEW` and `REJECTED` count as fraud-detection positives; `NEEDS_MORE_INFORMATION` and `VERIFICATION_ERROR` are not fraud accusations.
- A high review or information-request rate is workflow burden, not detection accuracy. Rejection requires high-confidence evidence in multiple dimensions.
- Synthetic labels and scenarios were authored in one project workflow; no independent author or human adjudication is available. Results are not estimates of real-world performance.
- Lexical/full-text deterministic checks are not semantic RAG and do not establish Gemini performance.
- Case-level explanations are in `case_level_predictions.csv`; exact inputs are in the versioned development JSONL.
- Dataset SHA-256: `74f4e53ed2697eab06b36a8bc303b22a6e9c3ff111392c40b09ba04b331de780`.
- V3 package SHA-256: `607770bd8a43d6c94ac836d21a8fd083fd17d1b5386982894b33494d321f840c`.
- No production code/configuration or previous benchmark was modified by this evaluator.
