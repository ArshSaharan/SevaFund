# SevaFund development-only verifier comparison

## Scope and reproducibility

This run evaluates 120 **synthetic** scenarios created specifically for development. It is an offline Python/lexical-retrieval evaluation: Gemini generation and embedding calls were disabled, and the run made zero Gemini API requests. The production verifier, thresholds, deployment configuration, original 200-case set, independent 100-case set, and prior run artifacts were not edited by this implementation.

Dataset: `development_scenarios_v1.jsonl` (SHA-256 `6eb46685656dd7ceaeea6971451738a6fd2a841ca2f0d2a5e02301eb7db7eb88`). It contains 48 legitimate, 48 fraudulent, and 24 borderline examples. Twelve scenario families each contain 4/4/2 examples and one document-source group; four families per category are assigned wholly to each of three folds. The run configuration and full predictions are in `run_config.json`, `baseline.json`, `candidate.json`, and `predictions.csv`.

Run command:

```sh
PYTHONPATH=. .venv/bin/python evaluation/evaluate_development_candidate.py
```

## Paired results

Fraudulent is the positive class. Legitimate **and borderline** cases are negative for binary detection metrics; review actions and follow-up burden are reported separately. A prediction is counted as flagged when it is `FLAG_FOR_REVIEW` or `REJECT`, or carries an explicit red flag. Review burden counts `FLAG_FOR_REVIEW`, `NEEDS_MORE_INFO`, and `REJECT`.

| Offline configuration | Precision | Recall | F1 | False-positive rate | Review burden | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| Existing Python heuristics + lexical retrieval | 34.04% | 66.67% | 45.07% | 86.11% | 94/120 (78.33%) | 0.34 ms |
| Development candidate + lexical retrieval | 100.00% | 100.00% | 100.00% | 0.00% | 72/120 (60.00%) | 0.08 ms |

| Configuration | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| Existing baseline | 32 | 62 | 16 | 10 |
| Development candidate | 48 | 0 | 0 | 72 |

The candidate issued 48 manual-review recommendations for the 48 fraudulent cases, requested more information for all 24 borderline cases, approved all 48 legitimate cases, and rejected none. Category-level candidate metrics are 100% precision/recall/F1 and 0% FPR in medical (40 cases), education (40), and community (40). Each of the three family-held-out folds also has the same binary result (16 TP, 24 TN, no FP/FN). Detailed per-family/source and per-class metrics are in `results.json`.

## Architecture added

- `app/services/development_verifier.py` is a separate candidate module. It reconciles retrieved text against the campaign story for explicit amount, beneficiary/payee, duration, quantity, reimbursement/prior-delivery, and authorized-purpose conflicts. It reports evidence as supporting, contradictory, incomplete, or unavailable.
- Candidate decisions are intentionally distinct: consistent retrieved support can be approved; an explicit contradiction is routed to manual review; absent or preliminary evidence requests more information. Rejection requires multiple independent conflict types plus an explicit document-fabrication signal. The development examples contain no such corroborated cases, so zero rejections is expected.
- `evaluation/generate_development_dataset.py` deterministically regenerates the development corpus; `evaluation/evaluate_development_candidate.py` compares the existing baseline and candidate on identical IDs and labels, with lexical retrieval forced and external calls disabled.
- `IND-064` and `IND-070` are read only by regression tests and are excluded from the development dataset and all reported metrics. Both now route to review.

## Interpretation and limitations

The observed candidate gains are supported **only for this constructed synthetic development set**. In this corpus the fraudulent label is directly associated with a designed document contradiction, legitimate records directly repeat the claim fields, and borderline documents explicitly say that approval/details are pending. This makes the classification task unusually separable and likely inflates the perfect scores. The narratives also share a generated structure within each family; the family/source folds avoid placing a family or source in multiple folds, but three folds are not a substitute for an independently authored test set.

The candidate is rule-based and the evidence retrieval is lexical. These results do not establish semantic retrieval quality, Gemini RAG performance, real-world fraud accuracy, calibrated risk, or production readiness. The sub-millisecond latency covers the local decision path in this environment; it excludes API, upload, OCR, and user review time. A 0% FPR on 72 non-fraud examples is not evidence that real-world false positives will be negligible.

The candidate was not tuned against either previous benchmark. The two legacy IDs were used only as fixed regression checks requested by the user. The first development run exposed a missed purpose conflict; the purpose matcher was corrected using a new unit test, and the final result is the later, separately saved run `development_candidate_20261115T161426Z`.

## Recommended next evaluation

Freeze the candidate code and decision policy, then have reviewers who did not author the scenarios create and adjudicate a new untouched set from realistic, de-identified cases. Split by beneficiary, institution, source document, and time so correlated records cannot cross partitions. Include true ambiguous cases and legitimate atypical expenses, blind reviewers to model outcomes, pre-register label/action mappings and metrics, and report confidence intervals plus workload by category. Run Gemini generation/embeddings only in a separately authorized, quota-checked evaluation and label those results independently from this offline lexical run. Do not change production based on this development result alone.
