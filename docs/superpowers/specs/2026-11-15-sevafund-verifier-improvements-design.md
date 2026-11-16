# SevaFund verification improvements: development design

## Intent

Improve SevaFund verification for claim/document contradictions, varied medical and nonmedical campaigns, legitimate cases currently routed unnecessarily to review, and fraud that lacks literal red-flag keywords. Keep outcomes that require more evidence distinct from confirmed fraud/rejection.

## Goals

- Build a fresh synthetic development corpus separate from both existing 200-case and 100-case benchmark files.
- Group cases by scenario family and document source so related examples can be kept together during development validation.
- Implement a development-only candidate verifier and compare it with the unchanged offline baseline on the same development cases.
- Keep offline heuristic/lexical results distinct from any Gemini generation or embedding results.
- Preserve existing scores, rules, thresholds, datasets, and reports as historical baselines.

## Non-goals and constraints

- Do not tune against either existing benchmark; treat the 100-case benchmark as consumed for diagnostics and reserve it from further development.
- Do not replace or alter the production verifier configuration in this implementation.
- Do not present lexical retrieval as semantic or Gemini RAG performance.
- Do not automatically reject a campaign based only on a single ambiguous document discrepancy.

## Approaches considered

1. **Development-only candidate verifier (recommended).** Add a separate candidate module and runner; leave the current service as the baseline. Compare both over one new, family/source-grouped development corpus. This provides a reproducible paired comparison without changing production behavior.
2. **Feature-flag the production service.** Add candidate settings to the live verifier. This reduces duplicated evaluation glue but increases the risk of accidentally running candidate logic in production and makes baseline isolation harder.
3. **Gemini-first evidence verifier.** Ask Gemini to reconcile claims and documents. This may improve semantic coverage but cannot currently be evaluated reliably under the known generation quota block, and it must remain a separate live configuration.

The recommended choice is a development-only candidate. Its first comparison is offline; a later Gemini/RAG run is reported separately after endpoint preflight and quota are available.

## Proposed architecture

- `evaluation/development_scenarios_v1.jsonl`: new synthetic examples with labels, `scenario_family`, `document_source`, category, claim, and attached evidence. Include consistent, contradictory, incomplete, and unavailable evidence, plus unusual-but-legitimate expenses and subtle financial/document fraud.
- `app/services/development_verifier.py`: isolated candidate implementation. It will produce category-aware plausibility and specificity signals plus evidence relations (`supports`, `contradicts`, `incomplete`, `unreadable`). Conflicts should increase review priority; rejection requires corroborated high-confidence evidence rather than mere absence or ambiguity.
- `evaluation/evaluate_development_candidate.py`: run baseline and candidate on identical cases and save per-case dimensions, action, evidence status, latency, metrics, hashes, and configuration in a new run directory.
- Validation partitions are grouped by scenario family and document source to reduce near-duplicate leakage. Development tuning and group-held-out validation use this corpus only.

## Decisions left to implementation

- Candidate weights and any candidate-only action cutoffs will be selected using grouped development validation, logged separately, and never written into the existing production settings.
- Report the current baseline settings beside candidate configuration; do not silently substitute candidate metrics for baseline results.
- Calculate fraud-positive precision, recall, F1, and false-positive rate with legitimate and borderline negative; additionally report review and rejection rates separately.
- If Gemini is available during development, record Gemini generation/embedding availability, success, latency, model configuration, and decisions in its own result set; never merge these rows into offline metrics.

## Acceptance criteria

- The original two benchmark JSONL files and prior run artifacts retain their hashes.
- The new development set meets declared class counts, has explicit grouping and evidence-source metadata, and contains no exact story duplicates from either existing benchmark.
- Baseline and candidate see identical case IDs and labels; per-case records preserve score dimensions and document-evidence status.
- Candidate changes and action settings are explicit and reproducible; original production thresholds and scoring implementation remain available and unchanged.
- Evaluation results state whether they are offline lexical, semantic-embedding, or Gemini generation results.
- Final guidance identifies that a fresh, untouched, independently adjudicated test set is needed after development.
