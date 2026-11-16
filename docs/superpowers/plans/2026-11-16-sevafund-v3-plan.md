# SevaFund Verification Engine V3 Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` task-by-task. Every implementation task starts with a failing test. V2 remains frozen.

**Goal:** Build, compare, freeze and run one synthetic final evaluation of a separate V3 verifier without changing production or consumed benchmarks.

**Architecture:** Create `app/services/development_verifier_v3/` as an independent package adapted from V2's modular pipeline. Add Decimal and currency-aware money parsing, source-attributed evidence facts, critical/optional evidence requirements, conservative decisions, and separately switchable components. Add grouped synthetic development data for paired V2/V3 evaluation and ablations. Freeze V3 before generating a separate 300-case synthetic final set; evaluate the frozen V2 and V3 exactly once on that set.

**Tech Stack:** Python 3.9, Pydantic, `decimal.Decimal`, existing PDF/text extraction, pytest, JSONL/JSON/CSV/Markdown.

**Spec:** `docs/superpowers/specs/2026-11-16-sevafund-v3-design.md`

## Global Constraints

- Production verifier and deployment are read-only for this work.
- Do not overwrite any existing corpus or result.
- V2's frozen package and configuration must remain unchanged; assert the manifest before paired runs.
- Never use previous 200-, 100-, 150- or V2 120-case labels to tune thresholds or rules.
- Gemini and API embeddings remain disabled; offline results are reported separately.
- Error, malformed-money, and unresolved material-contradiction paths cannot return approval.
- Generate the final 300-case corpus only after V3 freeze; run final V2/V3 comparison once; do not tune afterward.
- Synthetic single-author test data must not be described as independently authored or human-adjudicated.

## Review Focus

- A currency marker inside ordinary text (`papers,`, `years,`, `MRS`) must not parse as money; test root-boundary behavior.
- Foreign currencies and INR in the same dossier must never be numerically reconciled without a verified conversion.
- Invalid grouping, malformed decimals, written numbers, IDs, dates, and large values must be typed safely; all extraction failures block approval.
- Optional evidence gaps must not cause information requests; critical beneficiary/payment/core-claim gaps must.
- Individually plausible and internally consistent uploads are not issuer-authenticated; represent that uncertainty without asserting fraud.
- Category or cross-document ablations must operate on identical inputs and expose workload changes, not just accuracy.
- Family and document-source groups stay wholly within tune/validation partitions; final test uses entirely new families/sources.

---

### Task 1: Freeze inspection and V3 contracts

**Files:**
- Create: `app/services/development_verifier_v3/__init__.py`
- Create: `app/services/development_verifier_v3/schemas.py`
- Create: `app/services/development_verifier_v3/config.py`
- Test: `tests/test_development_verifier_v3.py`

**Interfaces:**
- `MoneyMention`: `raw`, `amount: Decimal | None`, `currency: str | None`, source span, `valid`, `issue`.
- `VerifierConfig`: V3-only feature switches for category, cross-document, currency parsing, requirement tiers and uncertainty policy; stable digest.
- `verify_case(CaseInput, config=DEFAULT_CONFIG) -> VerificationDecision` with all five V2-compatible decisions and auditable explanations.

- [ ] Add failing tests asserting V3 module absence, stable decision/schema contract, and frozen V2 source digest.
- [ ] Run tests and confirm expected failures.
- [ ] Define V3 typed contracts and feature config in the new package only.
- [ ] Run focused contract tests.

### Task 2: Currency-aware parser and provenance-safe extraction

**Files:**
- Create: `app/services/development_verifier_v3/money.py`
- Create: `app/services/development_verifier_v3/extraction.py`
- Test: `tests/test_development_verifier_v3.py`

**Interfaces:**
- `find_amounts(text) -> list[MoneyMention]` extracts only context-qualified amounts and retains ISO currency.
- `parse_amount_field(text, currency_context=None) -> MoneyMention` never raises; malformed/foreign-currency values remain explicit invalid mentions.
- Extracted amount facts carry `Decimal`, currency, semantic role, document/page/chunk source.

- [ ] Add red tests for INR/USD/GBP/EUR, lakh/crore, decimal/grouping, written values, dates/IDs/ordinary prose, `papers,`, malformed text, mixed currencies, and ambiguous symbols.
- [ ] Implement the standalone parser; never use binary floats for comparisons.
- [ ] Add tests that unlike currencies are not reconciled and malformed amounts cannot approve.
- [ ] Run parser and extraction tests.

### Task 3: V3 evidence pipeline and decision policy

**Files:**
- Create: `app/services/development_verifier_v3/{normalize,consistency,category,semantic,decision,audit,engine}.py`
- Test: `tests/test_development_verifier_v3.py`

**Interfaces:**
- Evidence findings distinguish supports, contradicts, missing, unreadable, and issuer-unverified.
- Requirement tier is `critical` or `optional`; only unsatisfied critical requirements request information.
- `verify_case` catches every stage error and returns `VERIFICATION_ERROR`; an error cannot approve.
- One material conflict routes to review; rejection needs two independent high-confidence material dimensions; unverified but consistent evidence is never described as authenticated.

- [ ] Add red tests for payment destination, cross-document person/identifier/date/service/amount/currency conflicts, source provenance, category-specific needs, optional gaps, and issuer-authenticity uncertainty.
- [ ] Add red tests for approval with sufficient readable evidence, no-document critical gap, reasonable uncertainty, and error never approving.
- [ ] Copy/adapt V2's generic extraction/consistency machinery into V3 without importing mutable V2 state or editing V2 files.
- [ ] Implement V3 tiered requirements, decision logic and audit output.
- [ ] Run V3 unit/regression tests plus unchanged V2 regression suite.

### Task 4: New grouped development corpus

**Files:**
- Create: `evaluation/generate_development_dataset_v3.py`
- Create: `evaluation/development_scenarios_v3.jsonl`
- Test: `tests/test_development_dataset_v3.py`

**Interfaces:**
- Deterministic 180-case synthetic set; 72 legitimate, 72 fraudulent, 36 borderline; 18 new families and source groups.
- 120 tune / 60 validation cases assigned by whole family/source; each of medical, education, community is represented in each split.
- Metadata includes `detectability`, source, family, adjudication rationale and synthetic marker; the engine receives only campaign fields and document text.

- [ ] Add failing count, balance, uniqueness, family/source split, evidence coverage, and novelty tests.
- [ ] Author new family narratives independently of the V2 generator and rules; do not read older benchmark rows for generation.
- [ ] Generate JSONL and validate its hash/structure.

### Task 5: Paired V2/V3 development evaluator and ablations

**Files:**
- Create: `evaluation/evaluate_development_candidate_v3.py`
- Test: `tests/test_evaluate_development_v3.py`

**Interfaces:**
- V2 and V3 receive identical cases and full document text; Gemini generation/embeddings/OCR are disabled.
- Primary detection does not count `NEEDS_MORE_INFORMATION`; report it as workload.
- Ablations: `without_category`, `without_cross_document`, `without_money`, `without_requirement_tiers`, `without_uncertainty_policy`, on the same IDs.
- Outputs: separate new run directory with per-case V2/V3/ablation predictions, case explanations, confusion matrices, class/category/fold metrics, auto-approval/workload/error/latency metrics, hashes, and report.

- [ ] Add failing tests for metric mapping, paired IDs/labels/doc inputs, ablation names, and no external API call.
- [ ] Implement the paired runner and freeze assertions for V2.
- [ ] Run focused tests, then one development comparison.
- [ ] Make any V3 changes only from tune-split evidence; document validation exposure; rerun development comparison with a new run ID.

### Task 6: Freeze V3

**Files:**
- Create: `evaluation/development_candidate_v3_freeze.json`
- Create: `evaluation/final_test_protocol_v3.md`
- Create: `evaluation/requirements-v3.txt`

- [ ] Freeze package/config and record per-file hashes, aggregate hash, dependency versions, development corpus hash, runner hash, and exposure statement.
- [ ] Specify the final test label/action mapping and one-shot execution before generating the final corpus.
- [ ] Assert V2 and V3 hashes match their manifests.

### Task 7: Generate and run the final 300-case synthetic set once

**Files:**
- Create: `evaluation/generate_final_test_v3.py`
- Create: `evaluation/final_test_v3.jsonl`
- Create: `evaluation/runs/final_v3_<timestamp>/...`

- [ ] Add generator/structure/novelty tests before creating test records.
- [ ] Generate 300 synthetic scenarios after the freeze: 100 per category, 120 legitimate, 120 fraudulent, 60 borderline, with new families and sources.
- [ ] Record the final dataset hash before model execution; verify family/source uniqueness and metadata separation.
- [ ] Run frozen V2 and V3 exactly once on identical cases; no changes after observing metrics.
- [ ] Report detection, false positives, fraudulent/legitimate auto-approval, class/category results, reviews, information requests, rejects, errors, latency, and case explanations; state single-author synthetic limitation.

### Task 8: Document conclusions

**Files:**
- Create: `docs/development_verifier_v3.md`
- Create: final run `report.md`

- [ ] Summarize supported results, remaining weaknesses, prior-data preservation hashes, independent-test limitations, and production recommendation.
- [ ] Do not describe synthetic, lexical or local semantic checks as Gemini or semantic-RAG accuracy.
