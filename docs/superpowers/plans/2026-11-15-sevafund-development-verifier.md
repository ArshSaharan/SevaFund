# SevaFund development-only verifier implementation plan

> **For agentic workers:** Native execution in this session; work task by task, preserving the original verifier as the baseline.

**Goal:** Build an isolated candidate verifier and a family/source-grouped synthetic development set, then compare baseline and candidate offline on identical cases.

**Architecture:** Keep `AIVerifierService`, production settings, and both old benchmarks unchanged. Put candidate evidence reconciliation in a separate module; use existing extraction and lexical retrieval but add explicit consistency signals to candidate decisions. A separate evaluator runs baseline and candidate, writes paired case-level outputs and reproducible reports, and makes no Gemini calls.

**Tech Stack:** Python 3, Pydantic verification schemas, existing RAG lexical retrieval, pytest for requested regression coverage, JSONL/CSV/JSON artifacts.

**Spec:** `docs/superpowers/specs/2026-11-15-sevafund-verifier-improvements-design.md`

## Global Constraints

- Preserve production scoring implementation, thresholds, and environment configuration.
- Preserve `evaluation/fundraising_scenarios.jsonl`, `evaluation/independent_benchmark_100.jsonl`, and all previous run artifacts.
- Do not use the existing 100-case diagnostic set to tune; `IND-064` and `IND-070` appear only in regression tests, not dev metrics.
- Do not make Gemini API calls or modify deployment configuration.
- Label all new scenarios synthetic; keep offline lexical, semantic, and Gemini outcomes separate.
- Candidate rejection requires corroborated high-confidence evidence; missing or ambiguous evidence must not alone reject.

## Review Focus

- Amount, identity, duration, reimbursement, and scope contradictions between claims and documents: test each mismatch type and confirm evidence is attributed to the correct campaign.
- Missing, unrelated, or unreadable documents: distinguish missing-information requests from fraud decisions.
- Legitimate unusual medical spending: category-aware reasons must not imply fraud from unfamiliar costs alone.
- Borderline evidence: preserve manual-review outcomes where evidence is partial or equivocal.
- Family/source leakage: assert each validation fold holds out whole scenario families and document-source groups.

---

### Task 1: Create a grouped development corpus

**Files:**
- Create: `evaluation/generate_development_dataset.py`
- Create: `evaluation/development_scenarios_v1.jsonl`
- Test: `tests/test_development_dataset.py`

**Interfaces:**
- Produces 120 synthetic records: 48 legitimate, 48 fraudulent, 24 borderline; 12 families with 10 cases each and 4/4/2 labels per family.
- Each row includes `scenario_family`, `document_source`, `evidence_relation`, category, story, documents, and stable ID.
- Four families each cover medical, education, and community campaigns; families and their source groups map wholly to one of three balanced group folds.

- [ ] Write failing checks for counts, unique IDs/stories, evidence metadata, and no family/source crossing folds.
- [ ] Run the focused dataset checks and confirm failure before generator implementation.
- [ ] Create original narratives and consistent, contradictory, incomplete, and absent evidence examples.
- [ ] Generate JSONL and verify exact label/fold balance and novelty against both existing corpora.

### Task 2: Implement the isolated candidate verifier

**Files:**
- Create: `app/services/development_verifier.py`
- Create: `tests/test_development_verifier.py`

**Interfaces:**
- Consumes campaign fields and retrieved evidence; returns the existing `VerificationResult` schema plus candidate-only evidence relation metadata.
- Reuses current red-flag and category-independent helpers without changing their code; applies candidate-only category-aware plausibility/specificity and contradiction checks.
- Actions: approval only with adequate support, review for substantiated suspicion/contradiction, needs-more-info for absent/incomplete proof, rejection only for multiple corroborated high-confidence fraud signals.

- [ ] Add failing unit tests for amount, identity, time-period, quantity, and reimbursement contradictions; missing/unreadable evidence; and legitimate unusual medical expenses.
- [ ] Add regression-only fixtures for `IND-064` and `IND-070`; assert neither is auto-approved and neither is rejected from a single mismatch.
- [ ] Run focused tests and observe expected failures before implementing candidate logic.
- [ ] Implement candidate-only behavior and pass unit/regression checks.

### Task 3: Build paired, grouped evaluation

**Files:**
- Create: `evaluation/evaluate_development_candidate.py`
- Test: `tests/test_development_evaluator.py`

**Interfaces:**
- Both baseline and candidate process identical case IDs, labels, and retrieved evidence.
- Split/aggregate by the supplied whole-family/source folds; no Gemini calls.
- Save baseline and candidate predictions separately plus paired summary, group metrics, hashes, and configuration.
- Report precision, recall, F1, FPR, confusion matrix, review rate, needs-more-info rate, rejection rate, and end-to-end latency.

- [ ] Test that baseline/candidate case ID and truth sets are identical and test metric definitions on a small hand-checkable fixture.
- [ ] Run tests red, then implement the runner and make them pass.
- [ ] Execute all 120 paired cases into a new run directory without overwriting earlier outputs.
- [ ] Verify dataset/source hashes and confirm zero Gemini calls.

### Task 4: Analyze and document results

**Files:**
- Create: `evaluation/runs/<new_run>/comparison_report.md`
- Create: `evaluation/runs/<new_run>/baseline.json`, `candidate.json`, `predictions.csv`, `run_config.json`

- [ ] Compare candidate with unchanged baseline overall and by class, category, family, document relation, and fold.
- [ ] State limitations, regression-test scope, and separate Gemini evaluation status.
- [ ] Recommend a fresh untouched, human-adjudicated test set for final evaluation; do not recommend production rollout from development metrics alone.
