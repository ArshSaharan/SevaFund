# Development re-scoring: original V3 vs existing vs improved V3 + Gemini

> **DEVELOPMENT, IN-SAMPLE: the improved policy was designed after inspecting these saved outputs.** It is not evidence of improvement and not an independent test. Policy `hybrid-v2-dev-1` (digest `00b8a03e36de1bd2`). Saved outputs of `gemini_eval_v1_3_6` (production prompt; the dated prompt is not exercised). No API call was made.

Existing rule reproduces every recorded combined decision: **True** (9 cases). Date reference: case submitted_on if present, else the evaluation run date 2026-11-16.

## Fraud detection and false positives (separately)

Detection = FLAG_FOR_REVIEW or REJECTED. 4 fraudulent, 6 non-fraud (4 legitimate + 2 borderline).

| System | Recall (fraud detected) | False-positive rate | Precision | F1 | TP/FP/FN/TN |
|---|---:|---:|---:|---:|---|
| Original V3 | 2/4 = 50% (15–85%) | 0/6 = 0% (0–39%) | 100% (34–100%) | 67% | 2/0/2/6 |
| Existing V3 + Gemini | 4/4 = 100% (51–100%) | 4/6 = 67% (30–90%) | 50% (22–78%) | 67% | 4/4/0/2 |
| Improved V3 + Gemini | 3/4 = 75% (30–95%) | 0/6 = 0% (0–39%) | 100% (44–100%) | 86% | 3/0/1/6 |

## Safety and workload

| System | Unsafe approvals (fraud/borderline approved) | Legitimate escalated | Manual reviews | Information requests | Verification errors | Approved → pending confirmation |
|---|---|---:|---:|---:|---:|---:|
| Original V3 | 3 ['V3T-064', 'V3T-084', 'V3T-194'] | 0 | 2 | 2 | 0 | 6 |
| Existing V3 + Gemini | 0  | 2 | 8 | 0 | 1 | 1 |
| Improved V3 + Gemini | 0  | 0 | 3 | 5 | 1 | 1 |

## API reliability and latency (same Gemini outputs for both hybrids)

Generation 19/20 succeeded; failures: ['SERVER_ERROR']; latency mean 45.5 s, median 45.1 s, p95 72.5 s. Both hybrids consume the same Gemini outputs; the improved policy adds no API calls or latency.

## Per case

| Case | Label | Gemini + RAG | Red flags | Original V3 | Existing | Improved | Improved trigger | Change |
|---|---|---|---:|---|---|---|---|---|
| V3T-064 | fraudulent | NEEDS_MORE_INFORMATION | 3 | APPROVED | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | REGRESSION |
| V3T-244 | fraudulent | REJECTED | 2 | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | GEMINI_EXPLICIT_FRAUD_WARNING | — |
| V3T-154 | fraudulent | FLAG_FOR_REVIEW | 3 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | V3_CONTRADICTION | — |
| V3T-044 | fraudulent | FLAG_FOR_REVIEW | 3 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | V3_CONTRADICTION | — |
| V3T-084 | borderline | NEEDS_MORE_INFORMATION | 3 | APPROVED | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | changed |
| V3T-194 | borderline | NEEDS_MORE_INFORMATION | 2 | APPROVED | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | changed |
| V3T-224 | legitimate | APPROVED | 0 | APPROVED | APPROVED | APPROVED | BOTH_APPROVE | — |
| V3T-104 | legitimate | NOT_RUN (HTTP 503) | 0 | APPROVED | VERIFICATION_ERROR | VERIFICATION_ERROR | GEMINI_FAILED:NOT_RUN | — |
| V3T-024 | legitimate | NEEDS_MORE_INFORMATION | 2 | APPROVED | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | changed |
| E150-102 | legitimate | NEEDS_MORE_INFORMATION | 2 | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | changed |

Vetoed model claims (deterministic date check) and unverified concerns:

* V3T-064 — vetoed: Retrieved document evidence contains a future date (07 September 2026) — No document issue date is after the reference date 2026-10-30.
* V3T-024 — unverified (not escalated): Geographical and institutional naming mismatch (Chitradurga is landlocked, yet pitch references a water crossing to Bay District Rehabilitation Service)
