# SevaFund development-only verifier comparison

## Scope and reproducibility

This run evaluates 120 **synthetic** scenarios created specifically for development. It is offline Python plus lexical retrieval: Gemini generation and embedding calls were disabled and the run made zero API requests. The production verifier, thresholds, deployment configuration, original 200-case set, independent 100-case set, and prior run artifacts were not edited by this implementation.

The dataset has 48 legitimate, 48 fraudulent, and 24 borderline cases. Twelve scenario families each contain 4/4/2 cases and one document-source group; four families per category are assigned wholly to each of three group folds. Dataset SHA-256: `6eb46685656dd7ceaeea6971451738a6fd2a841ca2f0d2a5e02301eb7db7eb88`. The run configuration and predictions are in `run_config.json`, `baseline.json`, `candidate.json`, `predictions.csv`, and `results.json`.

From the repository root, reproduce with:

```sh
PYTHONPATH=. .venv/bin/python evaluation/evaluate_development_candidate.py
```

The runner compares the baseline and candidate on identical case IDs, labels, and retrieval query construction. It also checks that retrieved-document counts match case by case. Gemini endpoints are force-disabled in-process.

## Paired results

Fraudulent is the positive class. Legitimate and borderline cases are negative for binary detection metrics; action and follow-up burden are also reported separately. A case is `flagged` for binary metrics when its action is `FLAG_FOR_REVIEW` or `REJECT`, or it has an explicit red flag. Review burden counts `FLAG_FOR_REVIEW`, `NEEDS_MORE_INFO`, and `REJECT`.

| Offline configuration | Precision | Recall | F1 | False-positive rate | Review burden | Mean decision latency |
|---|---:|---:|---:|---:|---:|---:|
| Existing Python heuristics + lexical retrieval | 34.04% | 66.67% | 45.07% | 86.11% | 94/120 (78.33%) | 0.34 ms |
| Development candidate + lexical retrieval | 100.00% | 100.00% | 100.00% | 0.00% | 72/120 (60.00%) | 0.07 ms |

| Configuration | TP | FP | FN | TN |
|---|---:|---:|---:|---:|
| Existing baseline | 32 | 62 | 16 | 10 |
| Development candidate | 48 | 0 | 0 | 72 |

The candidate recommended manual review for the 48 fraudulent cases, requested more information for all 24 borderline cases, approved all 48 legitimate cases, and rejected none. Candidate category-level precision/recall/F1 are 100% and FPR is 0% in medical, education, and community (40 cases each). Each family-held-out fold has 16 TP and 24 TN with no FP/FN. Detailed class, category, family, source, and fold summaries are saved in `results.json`.

## Candidate architecture

- `app/services/development_verifier.py` is a standalone development candidate and is not wired to production requests. It checks retrieved evidence for explicit amount, beneficiary/payee, duration, quantity, reimbursement/prior-delivery, and authorized-purpose conflicts, then labels evidence as supporting, contradictory, incomplete, or unavailable.
- Consistent, campaign-specific evidence can be approved; explicit contradictions go to manual review; missing or preliminary evidence requests more information. Rejection requires multiple independent conflicts plus an explicit document-fabrication signal. The corpus has no such corroborated case, so zero rejections is expected.
- `evaluation/generate_development_dataset.py` deterministically creates the development corpus. `evaluation/evaluate_development_candidate.py` runs both systems against the same cases and retrieval query, saves paired case-level decisions, metrics, hashes, and configuration.
- `IND-064` and `IND-070` are referenced only in regression tests, not in the dataset or reported metrics. Both tests assert the candidate does not approve or reject a single contradiction; both now route to review.

## Interpretation and limitations

The measured improvement is supported only for this constructed synthetic development set. Here, the fraudulent label is deliberately associated with a generated document contradiction, legitimate documents repeat claim fields, and borderline records explicitly mark details as pending. That makes cases unusually separable and likely inflates scores. Stories share a generated structure inside each family; group folds prevent family/source overlap, but do not make this an independently authored final test set.

This is a deterministic rule candidate using lexical retrieval. It does not establish semantic retrieval quality, Gemini RAG performance, real-world fraud accuracy, calibrated risk, or production readiness. The sub-millisecond latency is local decision time only; it excludes network, upload, OCR, and human-review time. A 0% FPR on 72 synthetic non-fraud cases is not evidence of negligible real-world false positives.

The candidate was not tuned against either previous benchmark. The two legacy cases were used only as fixed regression checks. An earlier development pass exposed a missed purpose conflict; a purpose-conflict unit test caught it, the candidate-only matcher was corrected, and this final run also aligned retrieval query construction between systems.

## Next evaluation

Freeze the candidate implementation and policy, then commission a new untouched, human-adjudicated test set authored by people who did not create the development scenarios. Split by beneficiary, institution, document source, and time to prevent correlated examples crossing partitions. Include ambiguous cases and legitimate atypical expenses, blind adjudicators to system decisions, pre-register label/action mappings and metrics, and report confidence intervals and workload by category. Evaluate Gemini generation/embeddings separately after endpoint preflight and explicit authorization. Do not change production based on this development evaluation alone.
