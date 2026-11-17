# Development comparison — development_candidate_v2_all_20261115T204852Z

Split: **all** · cases: 120 · labels: {'legitimate': 45, 'fraudulent': 45, 'borderline': 30} · Gemini calls: 0 · v2 matches freeze manifest: True

Fraudulent = positive class; legitimate and borderline = negative. Flag = FLAG_FOR_REVIEW or REJECTED (legacy engines also: any red flag). NEEDS_MORE_INFORMATION is not a fraud detection. Brackets: Wilson 95% intervals.

## Original vs improved

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
| Any human follow-up (not approved) | 31.7% | 52.5% | 65.0% |
| Mean latency (ms) | 0.59 | 0.46 | 5.63 |

## Confusion matrices (TP / FP / FN / TN)

| Engine | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| baseline | 13 | 25 | 32 | 50 |
| candidate_v1 | 11 | 21 | 34 | 54 |
| candidate_v2 | 39 | 4 | 6 | 71 |

## Decisions by ground truth

**baseline**

| Label | APPROVED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | REJECTED | VERIFICATION_ERROR |
|---|---:|---:|---:|---:|---:|
| legitimate | 32 | 0 | 13 | 0 | 0 |
| fraudulent | 32 | 0 | 13 | 0 | 0 |
| borderline | 18 | 0 | 12 | 0 | 0 |

**candidate_v1**

| Label | APPROVED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | REJECTED | VERIFICATION_ERROR |
|---|---:|---:|---:|---:|---:|
| legitimate | 23 | 4 | 13 | 0 | 5 |
| fraudulent | 24 | 4 | 11 | 0 | 6 |
| borderline | 10 | 12 | 7 | 0 | 1 |

**candidate_v2**

| Label | APPROVED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | REJECTED | VERIFICATION_ERROR |
|---|---:|---:|---:|---:|---:|
| legitimate | 39 | 3 | 3 | 0 | 0 |
| fraudulent | 3 | 3 | 37 | 2 | 0 |
| borderline | 0 | 29 | 1 | 0 | 0 |

## Category-wise

| Category | Engine | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit approved | NMI rate | TP/FP/FN/TN |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| COMMUNITY | baseline | 39.3% | 73.3% | 51.2% | 68.0% | 26.7% | 33.3% | 0.0% | 11/17/4/8 |
| COMMUNITY | candidate_v1 | 40.0% | 40.0% | 40.0% | 36.0% | 33.3% | 33.3% | 15.0% | 6/9/9/16 |
| COMMUNITY | candidate_v2 | 100.0% | 86.7% | 92.9% | 0.0% | 6.7% | 93.3% | 30.0% | 13/0/2/25 |
| EDUCATION | baseline | 25.0% | 6.7% | 10.5% | 12.0% | 93.3% | 93.3% | 0.0% | 1/3/14/22 |
| EDUCATION | candidate_v1 | 30.8% | 26.7% | 28.6% | 36.0% | 53.3% | 46.7% | 25.0% | 4/9/11/16 |
| EDUCATION | candidate_v2 | 76.5% | 86.7% | 81.2% | 16.0% | 6.7% | 73.3% | 27.5% | 13/4/2/21 |
| MEDICAL | baseline | 16.7% | 6.7% | 9.5% | 20.0% | 93.3% | 86.7% | 0.0% | 1/5/14/20 |
| MEDICAL | candidate_v1 | 25.0% | 6.7% | 10.5% | 12.0% | 73.3% | 73.3% | 10.0% | 1/3/14/22 |
| MEDICAL | candidate_v2 | 100.0% | 86.7% | 92.9% | 0.0% | 6.7% | 93.3% | 30.0% | 13/0/2/25 |

## Split-wise (family-held-out)

| Split | Engine | Precision | Recall | FPR | Legit approved | Cases |
|---|---|---:|---:|---:|---:|---:|
| tune | baseline | 27.8% | 18.5% | 28.9% | 77.8% | 72 |
| tune | candidate_v1 | 33.3% | 11.1% | 13.3% | 63.0% | 72 |
| tune | candidate_v2 | 100.0% | 88.9% | 0.0% | 96.3% | 72 |
| validation | baseline | 40.0% | 44.4% | 40.0% | 61.1% | 48 |
| validation | candidate_v1 | 34.8% | 44.4% | 50.0% | 33.3% | 48 |
| validation | candidate_v2 | 79.0% | 83.3% | 13.3% | 72.2% | 48 |

## Ablation (v2 components)

| Configuration | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit approved | Manual review | NMI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full | 90.7% | 86.7% | 88.6% | 5.3% | 6.7% | 86.7% | 34.2% | 29.2% |
| without_cross_document | 100.0% | 31.1% | 47.5% | 0.0% | 60.0% | 93.3% | 10.8% | 20.8% |
| without_category | 90.2% | 82.2% | 86.1% | 5.3% | 6.7% | 82.2% | 32.5% | 32.5% |
| without_semantic | 88.2% | 66.7% | 75.9% | 5.3% | 26.7% | 86.7% | 28.3% | 21.7% |
| requirements_only | n/a | 0.0% | 0.0% | 0.0% | 91.1% | 93.3% | 0.0% | 12.5% |

## Document-consistency detection (planted contradiction found as a material finding)

| Planted kind | Cases | v2 full | without cross-document | without semantic | without category |
|---|---:|---:|---:|---:|---:|
| amount | 6 | 100.0% | 0.0% | 100.0% | 100.0% |
| chronology | 4 | 100.0% | 0.0% | 100.0% | 100.0% |
| eligibility | 4 | 100.0% | 100.0% | 0.0% | 100.0% |
| identifier | 5 | 100.0% | 0.0% | 100.0% | 100.0% |
| identity | 4 | 100.0% | 0.0% | 100.0% | 100.0% |
| institution | 4 | 100.0% | 0.0% | 100.0% | 100.0% |
| payment_routing | 5 | 100.0% | 100.0% | 0.0% | 100.0% |
| service | 3 | 100.0% | 0.0% | 100.0% | 33.3% |
| settlement | 6 | 100.0% | 100.0% | 33.3% | 100.0% |

Overall: 100.0%. Legitimate cases with a material finding: 3; with any finding: 3. Borderline cases with a material finding: 1. Fraud without a planted contradiction: {'DV2-022': 'APPROVED', 'DV2-030': 'NEEDS_MORE_INFORMATION', 'DV2-062': 'NEEDS_MORE_INFORMATION', 'DV2-078': 'APPROVED', 'DV2-102': 'APPROVED', 'DV2-118': 'NEEDS_MORE_INFORMATION'}.

## Robustness to meaning-preserving perturbations (v2)

| Perturbation | Decision agreement | Recall | FPR | Changed cases |
|---|---:|---:|---:|---|
| currency_style | 96.7% | 86.7% | 10.7% | DV2-113 APPROVED→FLAG_FOR_REVIEW, DV2-114 APPROVED→FLAG_FOR_REVIEW, DV2-119 NEEDS_MORE_INFORMATION→FLAG_FOR_REVIEW, DV2-120 NEEDS_MORE_INFORMATION→FLAG_FOR_REVIEW |
| date_style | 100.0% | 86.7% | 5.3% | — |
| name_style | 100.0% | 86.7% | 5.3% | — |
| layout_collapse | 100.0% | 86.7% | 5.3% | — |

## Decisions by scenario variant

| Variant | Baseline | v1 | v2 |
|---|---|---|---|
| already_settled | APPROVED 4, FLAG_FOR_REVIEW 1 | APPROVED 2, FLAG_FOR_REVIEW 3 | FLAG_FOR_REVIEW 5 |
| already_settled+identity_mismatch | APPROVED 1 | APPROVED 1 | REJECTED 1 |
| ambiguous_identity | APPROVED 4 | APPROVED 3, FLAG_FOR_REVIEW 1 | NEEDS_MORE_INFORMATION 4 |
| amount_inflation | APPROVED 4, FLAG_FOR_REVIEW 2 | APPROVED 3, FLAG_FOR_REVIEW 3 | FLAG_FOR_REVIEW 6 |
| clean | APPROVED 11, FLAG_FOR_REVIEW 4 | APPROVED 9, FLAG_FOR_REVIEW 3, NEEDS_MORE_INFORMATION 1, VERIFICATION_ERROR 2 | APPROVED 14, FLAG_FOR_REVIEW 1 |
| consistent_fabricated | APPROVED 2, FLAG_FOR_REVIEW 1 | APPROVED 1, FLAG_FOR_REVIEW 1, VERIFICATION_ERROR 1 | APPROVED 3 |
| date_impossible | APPROVED 3, FLAG_FOR_REVIEW 1 | APPROVED 1, NEEDS_MORE_INFORMATION 1, VERIFICATION_ERROR 2 | FLAG_FOR_REVIEW 4 |
| estimate_revision | APPROVED 1 | FLAG_FOR_REVIEW 1 | APPROVED 1 |
| harmless_formatting | APPROVED 11, FLAG_FOR_REVIEW 4 | APPROVED 8, FLAG_FOR_REVIEW 4, NEEDS_MORE_INFORMATION 1, VERIFICATION_ERROR 2 | APPROVED 14, FLAG_FOR_REVIEW 1 |
| high_cost | FLAG_FOR_REVIEW 3 | APPROVED 3 | APPROVED 2, FLAG_FOR_REVIEW 1 |
| id_mismatch | APPROVED 3, FLAG_FOR_REVIEW 2 | APPROVED 2, FLAG_FOR_REVIEW 1, NEEDS_MORE_INFORMATION 1, VERIFICATION_ERROR 1 | FLAG_FOR_REVIEW 5 |
| identity_mismatch | APPROVED 3 | APPROVED 2, FLAG_FOR_REVIEW 1 | FLAG_FOR_REVIEW 3 |
| ineligible | APPROVED 2, FLAG_FOR_REVIEW 1 | APPROVED 3 | FLAG_FOR_REVIEW 3 |
| institution_mismatch | APPROVED 3, FLAG_FOR_REVIEW 1 | APPROVED 3, FLAG_FOR_REVIEW 1 | FLAG_FOR_REVIEW 4 |
| missing_required | APPROVED 1, FLAG_FOR_REVIEW 2 | APPROVED 1, NEEDS_MORE_INFORMATION 2 | NEEDS_MORE_INFORMATION 3 |
| modest_excess | APPROVED 7, FLAG_FOR_REVIEW 1 | APPROVED 3, FLAG_FOR_REVIEW 3, NEEDS_MORE_INFORMATION 1, VERIFICATION_ERROR 1 | NEEDS_MORE_INFORMATION 8 |
| no_documents | FLAG_FOR_REVIEW 8 | NEEDS_MORE_INFORMATION 8 | NEEDS_MORE_INFORMATION 8 |
| partial_goal | APPROVED 3 | APPROVED 2, FLAG_FOR_REVIEW 1 | APPROVED 3 |
| partial_paid | APPROVED 5 | FLAG_FOR_REVIEW 4, VERIFICATION_ERROR 1 | APPROVED 5 |
| payment_diversion | APPROVED 4 | APPROVED 4 | FLAG_FOR_REVIEW 4 |
| payment_diversion+ineligible | FLAG_FOR_REVIEW 1 | FLAG_FOR_REVIEW 1 | REJECTED 1 |
| provisional | APPROVED 7, FLAG_FOR_REVIEW 3 | APPROVED 4, FLAG_FOR_REVIEW 3, NEEDS_MORE_INFORMATION 3 | FLAG_FOR_REVIEW 1, NEEDS_MORE_INFORMATION 9 |
| service_mismatch | APPROVED 2, FLAG_FOR_REVIEW 1 | APPROVED 1, VERIFICATION_ERROR 2 | FLAG_FOR_REVIEW 3 |
| thin_evidence | APPROVED 1, FLAG_FOR_REVIEW 2 | APPROVED 1, NEEDS_MORE_INFORMATION 2 | NEEDS_MORE_INFORMATION 3 |

## v2 errors against ground truth

| Case | Label | Variant | Decision | Findings | Unmet requirements |
|---|---|---|---|---|---|
| DV2-022 | fraudulent | consistent_fabricated | APPROVED | — | — |
| DV2-030 | fraudulent | thin_evidence | NEEDS_MORE_INFORMATION | — | cost_evidence, clinical_record, institution_named |
| DV2-035 | legitimate | missing_required | NEEDS_MORE_INFORMATION | — | cost_evidence, clinical_record, institution_named |
| DV2-059 | legitimate | missing_required | NEEDS_MORE_INFORMATION | — | cost_evidence |
| DV2-062 | fraudulent | thin_evidence | NEEDS_MORE_INFORMATION | — | cost_evidence, enrolment_proof, institution_named |
| DV2-065 | legitimate | clean | FLAG_FOR_REVIEW | AMOUNT_EXCEEDS_BALANCE | — |
| DV2-066 | legitimate | harmless_formatting | FLAG_FOR_REVIEW | AMOUNT_EXCEEDS_BALANCE | — |
| DV2-067 | legitimate | high_cost | FLAG_FOR_REVIEW | AMOUNT_EXCEEDS_BALANCE | — |
| DV2-072 | borderline | provisional | FLAG_FOR_REVIEW | AMOUNT_EXCEEDS_BALANCE, DOCUMENT_NOT_FINAL | — |
| DV2-078 | fraudulent | consistent_fabricated | APPROVED | — | — |
| DV2-102 | fraudulent | consistent_fabricated | APPROVED | — | — |
| DV2-115 | legitimate | missing_required | NEEDS_MORE_INFORMATION | — | cost_evidence, itemised_budget |
| DV2-118 | fraudulent | thin_evidence | NEEDS_MORE_INFORMATION | — | cost_evidence, organisation_identity, itemised_budget, institution_named |

v1 runtime error types: {'ValueError': 12}. v1 cases where retrieval dropped a document: 0.

Synthetic development corpus authored together with the candidate. Results show behaviour on these scenario designs only and are not estimates of real-world accuracy.
