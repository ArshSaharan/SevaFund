# SevaFund independent synthetic evaluation — 150 cases

## Protocol and freeze

The benchmark followed the preregistered [protocol](../../independent_test_150_protocol.md). The candidate and baseline component SHA-256 values in that protocol were verified by the evaluator before processing. Neither verification engine was modified after results were observed. The 150-case dataset is separately authored, all-synthetic, and has 15 scenario families (five each in medical, education, and community), each with four legitimate, four fraudulent, and two borderline cases. All 150 IDs and labels were paired; retrieval counts matched for every case.

Dataset SHA-256: `099016d5da873766fccbd199337a153de62da1ee2b6c1bb8f35b9c5b43b510e0`. The benchmark contains cross-document conflicts, ambiguous/incomplete records, high justified medical costs, and fraud dossiers with mutually consistent-looking records. See the dataset's `adjudication_note` field for synthetic label rationale; this field is not sent to either verifier. Exact normalized-story duplicate checks against the prior 200-, 100-, and 120-case files passed.

All results below are **offline Python plus lexical retrieval**. Gemini generation and embeddings were disabled; zero Gemini calls were made. This is not semantic RAG or Gemini performance.

## Overall paired fraud-detection results

Fraudulent is positive. Legitimate and borderline are negative. Only `FLAG_FOR_REVIEW`, `REJECT`, or an emitted red flag counts as a fraud detection; `NEEDS_MORE_INFO` alone is not a fraud prediction.

| Engine | Precision | Recall | F1 | False-positive rate | Confusion matrix (TP / FP / FN / TN) |
|---|---:|---:|---:|---:|---:|
| Original Python heuristics + lexical retrieval | 14.12% | 20.00% | 16.55% | 81.11% | 12 / 73 / 48 / 17 |
| Frozen development candidate + lexical retrieval | 100.00% | 26.67% | 42.11% | 0.00% | 16 / 0 / 44 / 90 |

The candidate's 100% precision means all of its 16 fraud flags were fraudulent in this set. Its recall remains low: it missed 44 of 60 fraud cases. The four candidate runtime failures count as unflagged misses, not as detections.

## Category-wise results

| Category (n=50 each) | Engine | Precision | Recall | F1 | FPR | TP / FP / FN / TN |
|---|---|---:|---:|---:|---:|---:|
| Medical | Original | 0.00% | 0.00% | 0.00% | 83.33% | 0 / 25 / 20 / 5 |
| Medical | Candidate | 100.00% | 60.00% | 75.00% | 0.00% | 12 / 0 / 8 / 30 |
| Education | Original | 0.00% | 0.00% | 0.00% | 66.67% | 0 / 20 / 20 / 10 |
| Education | Candidate | 0.00% | 0.00% | 0.00% | 0.00% | 0 / 0 / 20 / 30 |
| Community | Original | 30.00% | 60.00% | 40.00% | 93.33% | 12 / 28 / 8 / 2 |
| Community | Candidate | 100.00% | 20.00% | 33.33% | 0.00% | 4 / 0 / 16 / 30 |

Candidate education performance is a serious weakness: it issued no fraud flags and missed all 20 fraudulent education cases. Community recall was also low at 20%. Medical recall was better but still missed 8 of 20 fraud cases.

## Review, follow-up, rejection, and system errors

These are action rates, separate from fraud detection. Manual review is `FLAG_FOR_REVIEW` only. Follow-up burden adds `NEEDS_MORE_INFO` and rejection.

| Engine | Manual review | Needs more information | Reject | Total follow-up burden | Auto-approve | System errors |
|---|---:|---:|---:|---:|---:|---:|
| Original | 85/150 (56.67%) | 0 (0.00%) | 0 (0.00%) | 85/150 (56.67%) | 65 (43.33%) | 0 |
| Candidate | 16/150 (10.67%) | 56/150 (37.33%) | 0 (0.00%) | 72/150 (48.00%) | 74 (49.33%) | 4/150 (2.67%) |

The candidate recommended more information for 22/60 legitimate cases (36.67%) and 22/30 borderline cases (73.33%). It flagged no legitimate or borderline cases as fraud. It did, however, auto-approve 28 fraudulent cases, request more information on 12 fraudulent cases, and fail to return a decision on four more. Neither engine rejected any case; this test did not exercise a supported basis for rejection.

The four candidate errors were `E150-095` through `E150-098`, all in the education exam-board family. The frozen verifier raised `ValueError` while parsing a substring of “papers,” as though its trailing “rs” were a rupee marker and the following comma were an amount. The harness records these as `SYSTEM_ERROR` and does not count them as fraud flags. No error message contents or credentials were logged.

Mean / median / p95 local end-to-end latency (retrieval plus decision): original 0.44 / 0.41 / 0.70 ms; candidate 0.68 / 0.42 / 1.96 ms. These timings exclude upload, OCR, external service calls, and human review.

## Case-pattern findings and limitations

- The candidate detected 16 fraud cases where the evidence matched its narrow direct checks. It missed many subtler cross-record facts: already completed and reimbursed sessions, a warranty exchange, prior issue under a grant, a closed or unavailable vessel window, and mismatched locations or schedules. Several fraud packages were internally consistent on names, item, and price; consistency alone led the candidate to `AUTO_APPROVE` despite another record undermining the claim.
- Of 44 candidate fraud misses, 28 were auto-approved, 12 were sent to `NEEDS_MORE_INFO`, and four failed with the amount parsing error. A request for more information is not counted as successful fraud detection.
- Legitimate incomplete and unusually expensive cases show the intended separation between fraud accusation and information requests: the candidate used `NEEDS_MORE_INFO` for some legitimate cases and did not fraud-flag any legitimate case. But its 36.67% legitimate information-request rate still represents beneficiary burden.
- The baseline generated 73 false-positive fraud flags among 90 legitimate/borderline cases, including 28 of 30 borderline cases. Its stronger review volume did not translate to good fraud recall.
- Labels and narratives are synthetic and author-assigned, not externally adjudicated real-case data. Some scenarios encode the decisive fact in an independent record while other submitted documents are internally consistent. Results measure this fixed challenge set, not production fraud prevalence. The zero candidate FPR and high candidate precision must not be interpreted as real-world estimates.

The independent dataset is frozen at `independent_test_150.jsonl`; the engine hashes are frozen and recorded in `run_config.json`. Any parser fix or rule change must be evaluated on a different new test set. Do not retune or re-score this benchmark. Production integration is not recommended from these results: candidate fraud recall, education coverage, and four runtime failures require a separate development cycle and a further untouched test set.
