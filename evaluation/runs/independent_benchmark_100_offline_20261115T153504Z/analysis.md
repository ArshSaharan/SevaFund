# Independent 100-case offline benchmark report

## Configuration and provenance

The benchmark is a new, fully synthetic corpus with 40 legitimate, 40 fraudulent, and 20 borderline campaigns. It was evaluated with the existing Python heuristic verifier and lexical retrieval; Gemini generation and embeddings were disabled. No thresholds or scoring code were changed. The saved prediction CSV contains all 100 cases.

Novelty checks found no exact story duplicates from the earlier 200-case dataset, no existing red-flag regex matches in campaign narratives or uploaded document text, and a maximum 5-word-shingle Jaccard similarity of 0.0000 between a new story and any old story. These checks support textual separation; they do not make a synthetic benchmark equivalent to a blinded real-world holdout.

## Overall results

| Metric | Result |
|---|---:|
| Cases | 100 |
| Precision | 40.0% |
| Recall | 95.0% |
| F1-score | 56.3% |
| False-positive rate | 95.0% |

Confusion matrix (fraudulent is positive; legitimate and borderline are negative):

| | Predicted fraud/flag | Predicted non-fraud |
|---|---:|---:|
| Actual fraudulent | TP 38 | FN 2 |
| Actual legitimate or borderline | FP 57 | TN 3 |

## Class-wise outcomes

| Class | N | Any flag | Review recommendation | Rejection | Red-flag match |
|---|---:|---:|---:|---:|---:|
| Legitimate | 40 | 39/40 (97.5%) | 39/40 (97.5%) | 0/40 (0.0%) | 0/40 (0.0%) |
| Fraudulent | 40 | 38/40 (95.0%) | 38/40 (95.0%) | 0/40 (0.0%) | 0/40 (0.0%) |
| Borderline | 20 | 18/20 (90.0%) | 18/20 (90.0%) | 0/20 (0.0%) | 0/20 (0.0%) |

Every flagged case received `FLAG_FOR_REVIEW`; there were no rejections and no red-flag matches in any class. Thus the 95% fraud recall is a review-queue rate, not a hard-fraud accusation rate. The 95% FPR means 57 of 60 non-fraud labels (39 legitimate and 18 borderline) were sent to review.

## Supporting-document consistency

The corpus contains 84 supporting-document cases: 26 legitimate cases with corroborating records, 40 fraudulent cases with a contradiction between the campaign claim and attached evidence, and 18 borderline cases with partial or unresolved evidence. Lexical retrieval returned at least one evidence chunk for all 84. The remaining 16 campaigns have no attachment.

| Evidence label | Cases with documents | Retrieved | Review | Auto-approved |
|---|---:|---:|---:|---:|
| Legitimate | 26 | 26 | 25 | 1 |
| Fraudulent | 40 | 40 | 38 | 2 |
| Borderline | 18 | 18 | 16 | 2 |

Two contradictory-document fraud cases were auto-approved:

- `IND-064` (`double_billed_books`, score 87.3): the claim asks for a second book payment, while the receipt says the set was delivered and acknowledged.
- `IND-070` (`training_duration`, score 83.6): the claim budgets a year, while the attached calendar covers a ten-week course.

This is consistent with the offline code path: retrieval supplies evidence, but local scoring uses supporting-document count for its documentation dimension; it does not compare document facts against campaign claims. In these cases, one retrieved document raises the score enough to cross the existing auto-approval threshold despite the mismatch. The evidence therefore tests a capability the offline heuristic path does not provide.

## Interpretation

This benchmark produces much lower precision and a much higher false-positive rate than the earlier synthetic set. Legitimate unusual medical costs and other low-specificity requests are heavily routed to review, while document contradictions are not reliably recognized. These results are measured on this newly authored synthetic corpus only; they do not estimate production performance or Gemini/RAG performance.

## Reproduction

Run from the repository root:

```bash
.venv/bin/python -B evaluation/evaluate_independent_benchmark_100.py --output-dir /Users/arshsaharan/Code/crowdfunding/evaluation/runs/independent_benchmark_100_offline_20261115T153504Z
```

Artifacts:

- Dataset: `evaluation/independent_benchmark_100.jsonl`
- Generator: `evaluation/generate_independent_benchmark_100.py`
- Evaluator: `evaluation/evaluate_independent_benchmark_100.py`
- Predictions: `predictions.csv` in this run directory
- Run configuration and source hashes: `run_config.json` in this run directory

Dataset SHA-256: `fc1188c2851342683a096f4235534d9d98deb3f390bd9840feb8b13b9a07aa46`.
