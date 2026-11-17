# Hybrid v3 offline before/after (no API call, development evidence only)

Policy `hybrid-v3-dev-1` (settings digest `a01273d9e3c89b0e`), created 2026-11-17T09:10:13.419044+00:00. DEVELOPMENT, IN-SAMPLE: the DA cases motivated these changes and the benchmark sets were used to develop V2/V3. No API call was made; Gemini outputs are scripted or saved.

## Part 1 - DA scenarios: decision by Gemini output (hybrid v2 -> hybrid v3)

| Case | Label | V3 | Gemini output | Hybrid v2 | Hybrid v3 | Review basis |
|---|---|---|---|---|---|---|
| DA-01 | legitimate | APPROVED | gemini_failed | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) |  |
| DA-01 | legitimate | APPROVED | gemini_approves | APPROVED (BOTH_APPROVE) | APPROVED (ALL_CHECKS_PASS) |  |
| DA-01 | legitimate | APPROVED | gemini_info_request_ungrounded_warning | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) |  |
| DA-01 | legitimate | APPROVED | gemini_flags_ungrounded | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_FRAUD_WARNING) | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_WARNING) | UNVERIFIED_MODEL_SUSPICION |
| DA-02 | legitimate | APPROVED | gemini_failed | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) |  |
| DA-02 | legitimate | APPROVED | gemini_approves | NEEDS_MORE_INFORMATION (EXPIRED_DOCUMENT) | NEEDS_MORE_INFORMATION (EXPIRED_DOCUMENT) |  |
| DA-02 | legitimate | APPROVED | gemini_info_request_ungrounded_warning | NEEDS_MORE_INFORMATION (EXPIRED_DOCUMENT) | NEEDS_MORE_INFORMATION (EXPIRED_DOCUMENT) |  |
| DA-02 | legitimate | APPROVED | gemini_flags_ungrounded | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_FRAUD_WARNING) | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_WARNING) | UNVERIFIED_MODEL_SUSPICION |
| DA-02 | legitimate | APPROVED | live_gemini_answer | NEEDS_MORE_INFORMATION (EXPIRED_DOCUMENT) | NEEDS_MORE_INFORMATION (EXPIRED_DOCUMENT) |  |
| DA-03 | fraudulent | FLAG_FOR_REVIEW | gemini_failed | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-03 | fraudulent | FLAG_FOR_REVIEW | gemini_approves | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-03 | fraudulent | FLAG_FOR_REVIEW | gemini_info_request_ungrounded_warning | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-03 | fraudulent | FLAG_FOR_REVIEW | gemini_flags_ungrounded | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-04 | legitimate | FLAG_FOR_REVIEW | gemini_failed | FLAG_FOR_REVIEW (V3_CONTRADICTION) | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) |  |
| DA-04 | legitimate | FLAG_FOR_REVIEW | gemini_approves | FLAG_FOR_REVIEW (V3_CONTRADICTION) | NEEDS_MORE_INFORMATION (V3_INFORMATION_REQUEST) |  |
| DA-04 | legitimate | FLAG_FOR_REVIEW | gemini_info_request_ungrounded_warning | FLAG_FOR_REVIEW (V3_CONTRADICTION) | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) |  |
| DA-04 | legitimate | FLAG_FOR_REVIEW | gemini_flags_ungrounded | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_WARNING) | UNVERIFIED_MODEL_SUSPICION |
| DA-05 | fraudulent | APPROVED | gemini_failed | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) | FLAG_FOR_REVIEW (CROSS_DOCUMENT_CONTRADICTION:DEATH_DATE_CONFLICT) | DETERMINISTIC_FINDING |
| DA-05 | fraudulent | APPROVED | gemini_approves | APPROVED (BOTH_APPROVE) | FLAG_FOR_REVIEW (CROSS_DOCUMENT_CONTRADICTION:DEATH_DATE_CONFLICT) | DETERMINISTIC_FINDING |
| DA-05 | fraudulent | APPROVED | gemini_info_request_ungrounded_warning | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) | FLAG_FOR_REVIEW (CROSS_DOCUMENT_CONTRADICTION:DEATH_DATE_CONFLICT) | DETERMINISTIC_FINDING |
| DA-05 | fraudulent | APPROVED | gemini_flags_ungrounded | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_FRAUD_WARNING) | FLAG_FOR_REVIEW (CROSS_DOCUMENT_CONTRADICTION:DEATH_DATE_CONFLICT) | DETERMINISTIC_FINDING |
| DA-06 | fraudulent | APPROVED | gemini_failed | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) |  |
| DA-06 | fraudulent | APPROVED | gemini_approves | APPROVED (BOTH_APPROVE) | APPROVED (ALL_CHECKS_PASS) |  |
| DA-06 | fraudulent | APPROVED | gemini_info_request_ungrounded_warning | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) |  |
| DA-06 | fraudulent | APPROVED | gemini_flags_ungrounded | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_FRAUD_WARNING) | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_WARNING) | UNVERIFIED_MODEL_SUSPICION |
| DA-07 | legitimate | APPROVED | gemini_failed | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) | VERIFICATION_ERROR (GEMINI_FAILED:SERVER_ERROR) |  |
| DA-07 | legitimate | APPROVED | gemini_approves | APPROVED (BOTH_APPROVE) | NEEDS_MORE_INFORMATION (FINANCIAL_EVIDENCE_MISSING) |  |
| DA-07 | legitimate | APPROVED | gemini_info_request_ungrounded_warning | NEEDS_MORE_INFORMATION (GEMINI_INFORMATION_REQUEST) | NEEDS_MORE_INFORMATION (FINANCIAL_EVIDENCE_MISSING) |  |
| DA-07 | legitimate | APPROVED | gemini_flags_ungrounded | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_FRAUD_WARNING) | FLAG_FOR_REVIEW (GEMINI_EXPLICIT_WARNING) | UNVERIFIED_MODEL_SUSPICION |
| DA-08 | fraudulent | FLAG_FOR_REVIEW | gemini_failed | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-08 | fraudulent | FLAG_FOR_REVIEW | gemini_approves | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-08 | fraudulent | FLAG_FOR_REVIEW | gemini_info_request_ungrounded_warning | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |
| DA-08 | fraudulent | FLAG_FOR_REVIEW | gemini_flags_ungrounded | FLAG_FOR_REVIEW (V3_CONTRADICTION) | FLAG_FOR_REVIEW (V3_CONTRADICTION) | DETERMINISTIC_FINDING |

## Part 2 - 10 historical cases (saved production-prompt outputs; in-sample)

| Case | Label | V3 | Hybrid v2 | Hybrid v3 | v3 trigger | Financial evidence |
|---|---|---|---|---|---|---|
| V3T-064 | fraudulent | APPROVED | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | SUPPORTED |
| V3T-244 | fraudulent | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | GEMINI_EXPLICIT_WARNING | MISSING |
| V3T-154 | fraudulent | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | V3_CONTRADICTION | MISSING |
| V3T-044 | fraudulent | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | V3_CONTRADICTION | SUPPORTED |
| V3T-084 | borderline | APPROVED | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | GEMINI_INFORMATION_REQUEST | SUPPORTED |
| V3T-194 | borderline | APPROVED | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | FINANCIAL_EVIDENCE_MISSING | MISSING |
| V3T-224 | legitimate | APPROVED | APPROVED | APPROVED | ALL_CHECKS_PASS | SUPPORTED |
| V3T-104 | legitimate | APPROVED | VERIFICATION_ERROR | VERIFICATION_ERROR | GEMINI_FAILED:NOT_RUN | SUPPORTED |
| V3T-024 | legitimate | APPROVED | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | FINANCIAL_EVIDENCE_UNTRACEABLE | UNTRACEABLE |
| E150-102 | legitimate | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | FINANCIAL_EVIDENCE_MISSING | MISSING |

## Part 3 - frozen benchmark sets, Gemini assumed to approve cleanly (deterministic layers only)

| Dataset | System | Fraud detected | Fraud approved | Legit escalated | Legit approved | Info requests | Manual reviews |
|---|---|---|---|---|---|---|---|
| final_test_300 | v3_alone | 60/100 | 20 | 0/100 | 100/100 | 100 | 60 |
| final_test_300 | hybrid_v2 | 60/100 | 20 | 0/100 | 100/100 | 100 | 60 |
| final_test_300 | hybrid_v3 | 60/100 | 20 | 0/100 | 90/100 | 120 | 60 |
| fundraising_200 | v3_alone | 20/80 | 0 | 0/80 | 80/80 | 100 | 20 |
| fundraising_200 | hybrid_v2 | 20/80 | 0 | 0/80 | 80/80 | 100 | 20 |
| fundraising_200 | hybrid_v3 | 20/80 | 0 | 0/80 | 72/80 | 108 | 20 |
| independent_test_150 | v3_alone | 10/60 | 36 | 0/60 | 45/60 | 59 | 10 |
| independent_test_150 | hybrid_v2 | 10/60 | 36 | 0/60 | 45/60 | 59 | 10 |
| independent_test_150 | hybrid_v3 | 10/60 | 0 | 0/60 | 0/60 | 140 | 10 |
| independent_benchmark_100 | v3_alone | 6/40 | 8 | 0/40 | 6/40 | 77 | 8 |
| independent_benchmark_100 | hybrid_v2 | 6/40 | 8 | 0/40 | 6/40 | 77 | 8 |
| independent_benchmark_100 | hybrid_v3 | 6/40 | 0 | 0/40 | 0/40 | 92 | 8 |

### final_test_300: reference date basis {'submitted_on': 300}

* hybrid v2 -> v3 transitions: {'legitimate': {'APPROVED -> APPROVED': 90, 'APPROVED -> NEEDS_MORE_INFORMATION': 10}, 'fraudulent': {'FLAG_FOR_REVIEW -> FLAG_FOR_REVIEW': 60, 'APPROVED -> APPROVED': 20, 'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 20}, 'borderline': {'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 80, 'APPROVED -> APPROVED': 10, 'APPROVED -> NEEDS_MORE_INFORMATION': 10}}
* cross-document findings (code|label): none
* financial evidence status by label: {'legitimate': {'SUPPORTED': 90, 'UNTRACEABLE': 10}, 'fraudulent': {'SUPPORTED': 60, 'MISSING': 40}, 'borderline': {'MISSING': 60, 'SUPPORTED': 30, 'NO_AMOUNT': 10}}
* V3 future-date findings refuted, by label: {'legitimate': 0, 'fraudulent': 0, 'borderline': 0}

### fundraising_200: reference date basis {'latest_document_date': 80, 'today_asia_kolkata': 120}

* hybrid v2 -> v3 transitions: {'legitimate': {'APPROVED -> APPROVED': 72, 'APPROVED -> NEEDS_MORE_INFORMATION': 8}, 'fraudulent': {'FLAG_FOR_REVIEW -> FLAG_FOR_REVIEW': 20, 'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 60}, 'borderline': {'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 40}}
* cross-document findings (code|label): none
* financial evidence status by label: {'legitimate': {'SUPPORTED': 72, 'MISSING': 8}, 'fraudulent': {'UNTRACEABLE': 12, 'MISSING': 68}, 'borderline': {'MISSING': 40}}
* V3 future-date findings refuted, by label: {'legitimate': 0, 'fraudulent': 0, 'borderline': 0}

### independent_test_150: reference date basis {'today_asia_kolkata': 150}

* hybrid v2 -> v3 transitions: {'legitimate': {'APPROVED -> NEEDS_MORE_INFORMATION': 45, 'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 15}, 'fraudulent': {'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 14, 'APPROVED -> NEEDS_MORE_INFORMATION': 36, 'FLAG_FOR_REVIEW -> FLAG_FOR_REVIEW': 10}, 'borderline': {'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 30}}
* cross-document findings (code|label): none
* financial evidence status by label: {'legitimate': {'MISSING': 36, 'NO_AMOUNT': 18, 'UNTRACEABLE': 6}, 'fraudulent': {'MISSING': 60}, 'borderline': {'MISSING': 24, 'UNTRACEABLE': 4, 'NO_AMOUNT': 2}}
* V3 future-date findings refuted, by label: {'legitimate': 0, 'fraudulent': 0, 'borderline': 0}

### independent_benchmark_100: reference date basis {'today_asia_kolkata': 100}

* hybrid v2 -> v3 transitions: {'legitimate': {'APPROVED -> NEEDS_MORE_INFORMATION': 6, 'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 34}, 'fraudulent': {'FLAG_FOR_REVIEW -> FLAG_FOR_REVIEW': 6, 'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 26, 'APPROVED -> NEEDS_MORE_INFORMATION': 8}, 'borderline': {'NEEDS_MORE_INFORMATION -> NEEDS_MORE_INFORMATION': 17, 'APPROVED -> NEEDS_MORE_INFORMATION': 1, 'FLAG_FOR_REVIEW -> FLAG_FOR_REVIEW': 2}}
* cross-document findings (code|label): none
* financial evidence status by label: {'legitimate': {'UNTRACEABLE': 5, 'MISSING': 31, 'NO_AMOUNT': 4}, 'fraudulent': {'UNTRACEABLE': 3, 'MISSING': 30, 'NO_AMOUNT': 7}, 'borderline': {'MISSING': 15, 'NO_AMOUNT': 3, 'UNTRACEABLE': 2}}
* V3 future-date findings refuted, by label: {'legitimate': 0, 'fraudulent': 0, 'borderline': 0}
