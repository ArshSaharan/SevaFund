# SevaFund V3 synthetic final evaluation

**One-time offline run on a new, synthetic 300-case corpus.** No Gemini calls, embeddings, semantic RAG, or issuer verification were used.
Primary binary metrics exclude borderline cases. Labels were authored in the project workflow; independent authorship and human adjudication were unavailable.

## V2 versus frozen V3

| Engine | N | Precision | Recall | F1 | FPR | Fraud auto-approved | Legit auto-approved | Manual review | Info request | Reject | Runtime errors | Mean / p50 / p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2_original | 300 | 100.0% | 50.0% | 66.7% | 0.0% | 0 (0.0%) | 0 (0.0%) | 16.7% | 83.3% | 0.0% | 0.0% | 2.59 / 2.30 / 5.34 |
| V3_frozen | 300 | 100.0% | 60.0% | 75.0% | 0.0% | 20 (20.0%) | 100 (100.0%) | 20.0% | 33.3% | 0.0% | 0.0% | 2.74 / 2.54 / 5.07 |

## V2_original confusion matrices

Binary fraud-vs-legitimate (borderline excluded):

| | Predicted fraud/review | Predicted approved |
|---|---:|---:|
| Actual fraudulent | 50 | 50 |
| Actual legitimate | 0 | 100 |

Three-class disposition:

| Actual \ Predicted | Approved | Flag/reject | Needs info/error |
|---|---:|---:|---:|
| legitimate | 0 | 0 | 100 |
| fraudulent | 0 | 50 | 50 |
| borderline | 0 | 0 | 100 |

Category-wise results:

| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| COMMUNITY | 100 | 100.0% | 66.7% | 80.0% | 0.0% | 20.0% | 80.0% |
| EDUCATION | 100 | 100.0% | 25.0% | 40.0% | 0.0% | 10.0% | 90.0% |
| MEDICAL | 100 | 100.0% | 66.7% | 80.0% | 0.0% | 20.0% | 80.0% |

## V3_frozen confusion matrices

Binary fraud-vs-legitimate (borderline excluded):

| | Predicted fraud/review | Predicted approved |
|---|---:|---:|
| Actual fraudulent | 60 | 40 |
| Actual legitimate | 0 | 100 |

Three-class disposition:

| Actual \ Predicted | Approved | Flag/reject | Needs info/error |
|---|---:|---:|---:|
| legitimate | 100 | 0 | 0 |
| fraudulent | 20 | 60 | 20 |
| borderline | 20 | 0 | 80 |

Category-wise results:

| Category | N | Precision | Recall | F1 | FPR | Manual review | Info request |
|---|---:|---:|---:|---:|---:|---:|---:|
| COMMUNITY | 100 | 100.0% | 66.7% | 80.0% | 0.0% | 20.0% | 50.0% |
| EDUCATION | 100 | 100.0% | 50.0% | 66.7% | 0.0% | 20.0% | 30.0% |
| MEDICAL | 100 | 100.0% | 66.7% | 80.0% | 0.0% | 20.0% | 20.0% |

## Fraud auto-approval analysis

Cases listed here were labeled fraudulent before verifier execution but received APPROVED. For the `consistent_fabrication` family, this is an expected limit: its visible documents agree, while the author-only provenance is not available to an offline verifier.

**V2_original: 0 fraudulent auto-approvals** — none.
**V3_frozen: 20 fraudulent auto-approvals** — V3T-061 (internally_consistent_but_forged_clinic_file), V3T-062 (internally_consistent_but_forged_clinic_file), V3T-063 (internally_consistent_but_forged_clinic_file), V3T-064 (internally_consistent_but_forged_clinic_file), V3T-065 (internally_consistent_but_forged_clinic_file), V3T-066 (internally_consistent_but_forged_clinic_file), V3T-067 (internally_consistent_but_forged_clinic_file), V3T-068 (internally_consistent_but_forged_clinic_file), V3T-069 (internally_consistent_but_forged_clinic_file), V3T-070 (internally_consistent_but_forged_clinic_file), V3T-161 (consistent_bursary_papers_forged), V3T-162 (consistent_bursary_papers_forged), V3T-163 (consistent_bursary_papers_forged), V3T-164 (consistent_bursary_papers_forged), V3T-165 (consistent_bursary_papers_forged), V3T-166 (consistent_bursary_papers_forged), V3T-167 (consistent_bursary_papers_forged), V3T-168 (consistent_bursary_papers_forged), V3T-169 (consistent_bursary_papers_forged), V3T-170 (consistent_bursary_papers_forged).

## Limitation and evidence status

- The cases and supporting documents are synthetic; one project agent authored them and assigned their labels. No independent author or human adjudicator validated the labels.
- The run is not a real-world accuracy estimate. The synthetic design contains repeated family-level structures even though those families are new relative to development data.
- A coherent fabricated dossier cannot be authenticated from internal consistency alone. Independent hospital, school, supplier, registry, beneficiary identity and platform payout checks are necessary before funds are released.
- Borderline campaigns are reported as unresolved/review/approval dispositions and are excluded from binary fraud metrics.
- This is offline heuristic/full-text verification, not Gemini, embeddings, or semantic RAG.
- V3 package SHA-256: `ba1b045e8b9d594891b6aaa4ac8c55b1758f48007a9d0261b177788f2363a7cd`.
- Final dataset SHA-256: `31f16ae955c4f85bf61f4fb69647f0997ada163341bb2a39ac725d2419b7b2a9`.
- Frozen configuration SHA-256: `3835a9c2e20bd30e079664ca775b22f1becf25176ad2b85e4c9bd14598bfc9e9`.
- No V2 or V3 engine code was modified after this run.

## Execution audit

The first runner attempt stopped before a paired evaluation completed. A second attempt completed and persisted all predictions, then failed while exporting CSV because two serializer fields were omitted. The CSV and this report were recovered from the persisted case predictions; V2 and V3 were not called again. See `metadata.json` and `results.json` for the attempt record.
