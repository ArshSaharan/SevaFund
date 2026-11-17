# SevaFund development-only verifier comparison

## Scope and reproducibility

This run evaluates 120 **synthetic** scenarios created for development. It is offline Python plus lexical retrieval: Gemini generation and embedding calls were disabled and the run made zero Gemini API requests. The production verifier, scoring thresholds, deployment settings, both prior datasets, and all prior evaluation artifacts were left untouched by this implementation.

The corpus contains 48 legitimate, 48 fraudulent, and 24 borderline cases. Twelve scenario families each contain 4/4/2 cases and one document-source group; four families per category are held together in each of three group folds. Dataset SHA-256: `6eb46685656dd7ceaeea6971451738a6fd2a841ca2f0d2a5e02301eb7db7eb88`. Full predictions, grouped metrics, and reproducibility hashes are in `results.json`, `predictions.csv`, `baseline.json`, `candidate.json`, and `run_config.json`.

Reproduce from the repository root with:

```sh
PYTHONPATH=. .venv/bin/python evaluation/evaluate_development_candidate.py
```

The runner force-disables Gemini, compares identical case IDs and labels, builds identical baseline/candidate retrieval queries, and checks retrieved-document counts match case by case.

## Paired results

Fraudulent is the positive class. Legitimate and borderline cases are negative for binary metrics. A case counts as flagged if it is recommended for `FLAG_FOR_REVIEW` or `REJECT`, or has an explicit red flag. Review burden counts `FLAG_FOR_REVIEW`, `NEEDS_MORE_INFO`, and `REJECT`.

| Offline configuration | Precision | Recall | F1 | False-positive rate | Review burden | Mean decision latency |
|---|---:|---:|---:|---:|---:|---:|
| Existing Python heuristics + lexical retrieval | 34.04% | 66.67% | 45.07% | 86.11% | 94/120 (78.33%) | 0.35 ms |
| Development candidate + lexical retrieval | 100.00% | 100.00% | 100.00% | 0.00% | 72/120 (60.00%) | 0.08 ms |

| Configuration | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| Existing baseline | 32 | 62 | 16 | 10 |
| Development candidate | 48 | 0 | 0 | 72 |

The candidate sent 48 fraudulent cases to review, requested more information for all 24 borderline cases, approved all 48 legitimate cases, and rejected none. It achieved the same binary result in each 40-case category and in each family-held-out fold. The detailed family/source/class breakdown is in `results.json`.

## Candidate architecture

- `app/services/development_verifier.py` is separate from the production request path. It checks retrieved evidence for explicit amount, payee/beneficiary, duration, quantity, reimbursement/prior-delivery, and authorized-purpose conflicts. It distinguishes supporting, contradictory, incomplete, and unavailable evidence.
- Category relevance is checked before approval: medical evidence needs medical-care context, education evidence needs student/course/institution context, and community evidence needs community/project context. Category mismatch or absent/preliminary proof requests more information.
- Consistent campaign-specific evidence can be approved; contradictions go to manual review; missing or incomplete evidence requests more information. Rejection requires multiple independent conflicts and an explicit document-fabrication indicator. This corpus contains no corroborated case meeting that rule, so no rejection is expected.
- `evaluation/generate_development_dataset.py` creates the synthetic set. `evaluation/evaluate_development_candidate.py` runs the existing baseline and candidate offline, saving paired predictions, metric definitions, latency, and hashes.
- `IND-064` and `IND-070` occur only in fixed regression tests. They are not part of this dataset or these metrics; both now route to review rather than approval or rejection.

## Interpretation and limits

The observed gain is supported only for this constructed synthetic development corpus. Fraud labels are deliberately paired with generated document contradictions, legitimate documents repeat claims consistently, and borderline documents explicitly indicate pending details. These cues make the task unusually separable and likely inflate the perfect scores. Narratives have a generated structure within each family; keeping complete families/sources within folds prevents cross-fold family leakage but does not make this an independently authored test set.

The candidate is deterministic rule logic over lexical retrieval. This result does not establish semantic retrieval quality, Gemini RAG performance, real-world fraud accuracy, risk calibration, or production readiness. Sub-millisecond latency covers local decision processing only; it excludes network, upload, OCR, and human-review time. A zero false-positive rate on 72 synthetic negative examples is not evidence of a low production FPR.

The candidate was not tuned against either old benchmark. The two previous benchmark IDs were used only for the requested regression tests. A prior development pass found a missed purpose conflict; a new unit test drove the fix. The final run also uses identical retrieval-query construction and includes a tested category-relevance check.

## Recommended next evaluation

Freeze this candidate and have independent reviewers author and adjudicate a new untouched test set from realistic, de-identified cases. Partition by beneficiary, institution, document source, and time to avoid correlated records crossing partitions. Include ambiguous requests and legitimate unusual expenses; blind adjudicators to system decisions; pre-register label/action mapping and metrics; report confidence intervals and category-level workload. Evaluate Gemini generation and embeddings separately after explicit authorization and endpoint/quota preflight. Do not alter production based on development results alone.
