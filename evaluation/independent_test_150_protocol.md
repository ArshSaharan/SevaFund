# Independent SevaFund verifier evaluation protocol (150 cases)

## Preregistration and freeze

This protocol is recorded before generating or evaluating the new cases. The corpus is a synthetic, independently authored test set; no stories, scenario-family definitions, document narratives, labels, or scoring rules are copied from `development_scenarios_v1.jsonl`. Results are test-only and will not be used to alter either engine.

The candidate and baseline are frozen at these SHA-256 values before benchmark generation:

| Component | SHA-256 |
|---|---|
| Candidate `app/services/development_verifier.py` | `f6bba947d5ec1202502ece19e02fdf24b93cdb623a12a59d6eced670118e4eec` |
| Baseline `app/services/ai_verifier.py` | `3a3b857c8bf658d1400b1a9c92eb1f19a60a405e17ba86199be7298bcd1bc9c8` |
| Baseline rules `app/services/fraud_detector.py` | `f47e641743d1d66272cf36d6bfa2053245bbf2b68bf15b19075fab41cf97279f` |
| Retrieval `app/services/rag.py` | `95b14980be44fd6b658cd4025a0c24a90447a53fb212f42cede257b2f4f71309` |
| Baseline configuration `app/config.py` | `edb58aa33fb33fd2dee8dea167b851f524ac1338f0560b13006b6928723d4bb3` |
| Verification schema `app/schemas/ai.py` | `8384f9a64fc3c3fb407409366606fc796adcce5257a02c33de03a7512a962317` |

These modules, scoring logic, thresholds, and benchmark records are not to be changed after evaluation. The evaluator and benchmark authoring artifacts are separate from both engines. Any discovered defect is reported for a later development cycle; it is not repaired and re-scored on this test set.

## Dataset plan

- 150 unique synthetic campaigns: 60 legitimate, 60 fraudulent, and 30 borderline.
- Three broad categories, equally represented overall: 50 medical, 50 education, and 50 community cases.
- Fifteen new scenario families (five per category), each with a distinct primary document-source group. Ten cases per family use a 4 legitimate / 4 fraudulent / 2 borderline allocation. Families are metadata for distribution analysis only; the engine does not receive labels, family labels, or adjudication notes.
- Required content includes multi-document contradictions, legitimate incomplete/unusual records, apparently plausible and mutually consistent paperwork for some fraudulent cases, high but supported medical expenses, and ambiguous cases for which more information is preferable to rejection.
- `synthetic: true` is included on every row. These labels are author-assigned scenario ground truth, not externally adjudicated real-case outcomes.
- Novelty checks require unique IDs and campaign stories and no exact normalized story match against either previous benchmark. This protocol, corpus, and result directory are separate from the existing development and diagnostic artifacts.

## Paired evaluation and metrics

Both systems receive the same campaign input and the same uploaded-document texts, processed through the same offline lexical retrieval query and ranking. Gemini generation and embedding calls are disabled. Retrieval-count mismatches invalidate the paired comparison.

For binary fraud detection, fraudulent is positive; legitimate and borderline are negative. A case is detection-flagged only when the engine returns `FLAG_FOR_REVIEW` or `REJECT`, or emits a red flag. `NEEDS_MORE_INFO` alone is not counted as fraud detected. This definition prevents the review queue from inflating fraud recall.

Report precision, recall, F1, false-positive rate, and TP/FP/FN/TN confusion matrices overall and separately for medical, education, and community. Report actions independently: `FLAG_FOR_REVIEW` rate, `NEEDS_MORE_INFO` rate, `REJECT` rate, and total follow-up/review burden (`FLAG_FOR_REVIEW` + `NEEDS_MORE_INFO` + `REJECT`). Report borderline action rates separately. Latency is end-to-end local retrieval plus decision processing, with mean, median, and p95; it excludes file upload, external calls, OCR, and human work.

The same metrics are computed for baseline and candidate using identical case IDs and labels. Category-wise and class-wise summaries use the same binary mapping. Missing denominators are reported as `null`; no metrics are optimized after examining this set.

## Interpretation boundary

All results are offline Python plus lexical retrieval. They do not measure Gemini generation, Gemini embeddings, or semantic RAG. Synthetic performance cannot establish real-world fraud accuracy or justify production deployment. Report misses, false positives, false approvals, and review/rejection behavior without retuning; use a new test set for any subsequent candidate version.
