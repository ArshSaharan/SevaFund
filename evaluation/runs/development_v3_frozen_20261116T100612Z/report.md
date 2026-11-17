# SevaFund V3 paired development evaluation

Synthetic development data only. No Gemini calls, embeddings, semantic RAG, or external issuer verification were used.
Primary binary classification metrics exclude borderline cases; borderline outcomes are reported separately.

## V2 versus V3

| Engine | N | Precision | Recall | F1 | FPR (legitimate) | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Reject | Runtime errors | Mean / p50 / p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2_original | 180 | 100.0% | 16.7% | 28.6% | 0.0% | 0 (0.0%) | 0 (0.0%) | 5.6% | 94.4% | 0.0% | 0.0% | 3.07 / 2.78 / 5.82 |
| V3_full | 180 | 100.0% | 50.0% | 66.7% | 0.0% | 30 (50.0%) | 60 (100.0%) | 16.7% | 33.3% | 0.0% | 0.0% | 2.50 / 2.62 / 3.87 |

### V2_original confusion matrices

Binary fraud-versus-legitimate (borderline excluded):

| | Predicted fraud/review | Predicted approved |
|---|---:|---:|
| Actual fraudulent | 10 | 50 |
| Actual legitimate | 0 | 60 |

Three-class disposition matrix:

| Actual \ Predicted | Approved | Flag/reject | Needs info/error |
|---|---:|---:|---:|
| legitimate | 0 | 0 | 60 |
| fraudulent | 0 | 10 | 50 |
| borderline | 0 | 0 | 60 |

Category-wise adjudicable metrics:

| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| COMMUNITY | 60 | — | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| EDUCATION | 60 | — | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| MEDICAL | 60 | 100.0% | 50.0% | 66.7% | 0.0% | 16.7% | 83.3% |

Grouped validation split (families held out from development split):

| Split | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 90 | 100.0% | 33.3% | 50.0% | 0.0% | 11.1% | 88.9% |
| validation | 90 | — | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |

Borderline outcomes: APPROVED: 0, NEEDS_MORE_INFORMATION: 60, FLAG_FOR_REVIEW: 0, REJECTED: 0, VERIFICATION_ERROR: 0.

### V3_full confusion matrices

Binary fraud-versus-legitimate (borderline excluded):

| | Predicted fraud/review | Predicted approved |
|---|---:|---:|
| Actual fraudulent | 30 | 30 |
| Actual legitimate | 0 | 60 |

Three-class disposition matrix:

| Actual \ Predicted | Approved | Flag/reject | Needs info/error |
|---|---:|---:|---:|
| legitimate | 60 | 0 | 0 |
| fraudulent | 30 | 30 | 0 |
| borderline | 0 | 0 | 60 |

Category-wise adjudicable metrics:

| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| COMMUNITY | 60 | 100.0% | 50.0% | 66.7% | 0.0% | 16.7% | 33.3% |
| EDUCATION | 60 | 100.0% | 50.0% | 66.7% | 0.0% | 16.7% | 33.3% |
| MEDICAL | 60 | 100.0% | 50.0% | 66.7% | 0.0% | 16.7% | 33.3% |

Grouped validation split (families held out from development split):

| Split | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| development | 90 | 100.0% | 100.0% | 100.0% | 0.0% | 33.3% | 33.3% |
| validation | 90 | — | 0.0% | 0.0% | 0.0% | 0.0% | 33.3% |

Borderline outcomes: APPROVED: 0, NEEDS_MORE_INFORMATION: 60, FLAG_FOR_REVIEW: 0, REJECTED: 0, VERIFICATION_ERROR: 0.

## V3 ablations

Each variant uses the same 180 cases. These are component contribution measurements, not independent test results.

| Variant | Precision | Recall | F1 | FPR | Fraud auto-approved | Manual review | Info request | Reject | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_v3 | 100.0% | 50.0% | 66.7% | 0.0% | 30 | 16.7% | 33.3% | 0.0% | 0.0% |
| without_category_awareness | 100.0% | 50.0% | 66.7% | 0.0% | 30 | 16.7% | 27.8% | 0.0% | 0.0% |
| without_cross_document_checks | — | 0.0% | 0.0% | 0.0% | 30 | 0.0% | 50.0% | 0.0% | 0.0% |
| without_improved_financial_parsing | 100.0% | 50.0% | 66.7% | 0.0% | 10 | 16.7% | 72.2% | 0.0% | 0.0% |
| without_tiered_evidence_requirements | 100.0% | 50.0% | 66.7% | 0.0% | 0 | 16.7% | 83.3% | 0.0% | 0.0% |
| without_uncertainty_policy | 100.0% | 50.0% | 66.7% | 0.0% | 0 | 16.7% | 83.3% | 0.0% | 0.0% |

## Method and limits

- Both versions receive the same case IDs, labels, structured campaign fields, and document text. V2 does not receive V3-only goal-currency metadata.
- Fraud precision/recall/F1/FPR use the 120 legitimate/fraudulent scenarios; borderline cases are excluded from binary metrics and shown in the 3-class disposition matrix.
- `FLAG_FOR_REVIEW` and `REJECTED` count as fraud-detection positives; `NEEDS_MORE_INFORMATION` and `VERIFICATION_ERROR` are not fraud accusations.
- A high review or information-request rate is workflow burden, not detection accuracy. Rejection requires high-confidence evidence in multiple dimensions.
- Synthetic labels and scenarios were authored in one project workflow; no independent author or human adjudication is available. Results are not estimates of real-world performance.
- Lexical/full-text deterministic checks are not semantic RAG and do not establish Gemini performance.
- Case-level explanations are in `case_level_predictions.csv`; exact inputs are in the versioned development JSONL.
- Dataset SHA-256: `683bbcd84eab11b4f468df87ae69317f28ee0877b94184dea5bbb047c6843d8f`.
- V3 package SHA-256: `ba1b045e8b9d594891b6aaa4ac8c55b1758f48007a9d0261b177788f2363a7cd`.
- No production code/configuration or previous benchmark was modified by this evaluator.
