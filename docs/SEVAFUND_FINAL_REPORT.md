# SevaFund fraud-verification prototype: final technical report

**Date:** 2026-11-17. **Branch:** `dev/verifier-v2-v3-evaluation` (local only; nothing pushed, merged or deployed).
**Final candidate:** hybrid v4, policy `hybrid-v4-dev-1`, settings digest `a4f5b7e7ae280dc4`, development only.

> **How to read the numbers in this report.** Every result in §6–§7 comes from a **developer-designed synthetic
> evaluation, not independent validation**:
> - The same person who built the system wrote the 60 scenarios.
> - Gemini's answers are scripted.
> - External confirmations are simulated.
>
> The results show how the logic behaves on cases written to exercise it. They do not estimate real-world fraud
> detection, and the simulated confirmations do not show that real-world verification works.

---

## 1. Executive summary

SevaFund's fraud-verification prototype now has one rule at its centre: **no campaign can raise or release money until
four facts are confirmed through contacts the campaigner does not control**:
- the beneficiary;
- the institution;
- the payment destination;
- the requested amount.

Automated checks (frozen V3's deterministic rules, Gemini with evidence grounding, date and cross-document checks) can
only do four things:
- refer a campaign to a human;
- ask for information;
- grant *provisional* approval;
- report that verification failed.

Gemini cannot reject anything. Every decision carries an explanation, and every event is written to a tamper-evident
audit log.

**This cycle's changes (hybrid v4, built on the unchanged hybrid v3).**
1. **Independent amount confirmation before activation.** This closes the main remaining safety gap: inflated goals
   backed by consistent documents.
2. **A deterministic payment-account check.** It flags documents that give conflicting bank details.
3. **A fair assisted route for genuine applicants without formal quotations.** A caseworker obtains the amount from the
   cost issuer, and the same four checks still apply.
4. **Explanations with evidence and a hash-chained audit log.**

**Final evaluation (60 developer-designed scenarios; identical inputs and scripted Gemini answers for every system).**

| | Frozen V3 | Hybrid v2 | Hybrid v3 (previous candidate) | **Hybrid v4 (final)** |
|---|---|---|---|---|
| Fraud activated, simulated (of 25) | 5 (20%) | 4 (16%) | 4 (16%) | **1 (4%)** |
| Fraud detected, detectable from documents (of 15) | 8 (53%) | 11 (73%) | 12 (80%) | **14 (93%)** |
| Activations without independent amount confirmation | 30 of 30 | 17 of 17 | 17 of 17 | **0 of 19** |
| False positives (of 25 legitimate) | 2 (8%) | 5 (20%) | 3 (12%) | 3 (12%) |
| Legitimate complete approved (of 15) | 14 (93%) | 10 (67%) | 12 (80%) | 12 (80%) |
| Legitimate incomplete activated, simulated (of 10) | 7 (70%)\* | 1 (10%) | 0 (0%) | **6 (60%)** |

\* Frozen V3 has no cost-evidence gate. It provisionally approves 7 of the 10 incomplete cases, and also 14 of the 25
fraud cases.

**The one fraud case that still activates is collusive.** The supplier itself confirms the inflated price, so no
independent party reveals the fraud (§8).

**The price of the amount check:** one genuine campaign stays pending, because its hospital billing desk could not be
reached.

**Is it ready?** The prototype is complete and ready for a **local demonstration** (`docs/FINAL_PROTOTYPE_README.md`).
It is **not production-ready**:
- it is not wired into the live application;
- confirmations are simulated;
- the evaluation is not independent.

---

## 2. Final architecture

```
Campaign (title, story, goal, beneficiary, documents, submission date)
   │
   ├─ Retrieval: production rag.retrieve_evidence (no-embedding fallback in the evaluation)
   ├─ Gemini (frozen hybrid-v2 client and date-aware prompt; scripted offline)  ──┐
   ├─ Frozen V3 deterministic verifier (development_verifier_v3)                  │
   │                                                                              ▼
   ├─ Frozen hybrid v3 policy (development_hybrid_v3, called unchanged):
   │     event-aware dates · cross-document contradictions · financial-evidence gate ·
   │     Gemini concerns escalate only when their quote is found in the documents · Gemini never rejects
   │
   └─ Hybrid v4 (development_hybrid_v4)
         policy.py    payment-account check · assisted cost route · findings, evidence and explanation
         workflow.py  four-check activation workflow (BENEFICIARY, INSTITUTION, PAYMENT_DESTINATION, AMOUNT)
         audit.py     hash-chained audit log
         payment.py   PAYMENT_ACCOUNT_CONFLICT
```

| Component | Location | Status |
|---|---|---|
| Production verifier and app | `app/services/ai_verifier.py`, `app/routers`, `app/config.py` (default model `gemini-3.8-flash`) | **Unchanged** in this cycle; does not use the prototype |
| Frozen V3 | `app/services/development_verifier_v3` (commit `1c7e739`) | Frozen, verified unchanged |
| Hybrid v2 | `app/services/development_gemini_verification` (freeze `b9f7514`) | Frozen, verified unchanged |
| Hybrid v3 | `app/services/development_hybrid_v3` (freeze `e7b3688`, fingerprint `2d117adb…40f8`) | Frozen, verified unchanged |
| Frozen approval workflow | `app/services/development_approval_workflow` | Unchanged; v4 reuses its states, contact sources and campaign-contact rule |
| **Hybrid v4** | `app/services/development_hybrid_v4` (commit `3a1abe3`) | New; development only; production imports nothing from it (tested) |
| Final evaluation | `evaluation/final_evaluation/` (commit `545df85`) | New |
| Independent v5 evaluation kit | `evaluation/independent_v5/`, `evaluation/independent_test_v5/` | Preserved for future use, not run |

**Design choices:**
- **No frozen code was edited.** Hybrid v4 calls hybrid v3's `combine` as a function and adds its own layer on top.
- **Activation is separate from the decision.** The automated decision can never produce VERIFIED_ACTIVE; only
  `record_confirmation` can, and only when all four checks are satisfied.

---

## 3. Fraud-verification workflow

| Step | What happens | Possible outcomes |
|---|---|---|
| 1. Automated checks | Frozen V3 rules, date model, cross-document checks, financial-evidence gate, payment-account check, Gemini concerns with grounding | APPROVED (provisional) · NEEDS_MORE_INFORMATION · FLAG_FOR_REVIEW · REJECTED (only V3's deterministic multi-contradiction rule) · VERIFICATION_ERROR |
| 2. Provisional approval | APPROVED becomes ELIGIBLE_PENDING_CONFIRMATION. Nothing is public and no money moves | Four required checks are opened |
| 3. Independent confirmation | Each check is confirmed through an independently sourced contact (official registry or directory, platform KYC, a prior verified record). A contact supplied by the campaign, or found in its own text, is recorded but never counts | CONFIRMED satisfies the check · CONTRADICTED sends the campaign to FLAG_FOR_REVIEW · UNREACHABLE or INCONCLUSIVE leave it open |
| 4. Amount check | The cost issuer states the amount due and anything already covered (insurance, scheme, scholarship, advance). The goal must be at most (stated − covered) × 1.05 | Within tolerance: satisfied · Above: FLAG_FOR_REVIEW · No figure: open |
| 5. Activation | VERIFIED_ACTIVE only when all four checks are independently confirmed | Disbursement is limited to the confirmed need |
| Missing quotation | If cost evidence is the only open item, the information request lists acceptable alternatives and offers the **assisted route**: a caseworker obtains the amount from the cost issuer | Leads to step 3 with the same four checks |
| Review | A reviewer can clear, request information or reject. Reviewers can never activate, and clearing a campaign voids all earlier confirmations | — |

**Every step is written to the audit log:**
- the automated decision with its full explanation;
- each confirmation attempt;
- each state change.

Each entry's hash covers its content and the previous entry's hash, so any edit, deletion or reordering is detected.

---

## 4. Important improvements in this cycle

| # | Weakness (from the hybrid v3 freeze limitations) | Hybrid v4 change | How it is tested |
|---|---|---|---|
| 1 | The amount was never independently confirmed. An inflated goal with consistent documents could activate | AMOUNT is a fourth required check. Other payers are deducted, with 5% tolerance. Disbursement is capped at the confirmed need | 6 parameterised tolerance cases; issuer with no figure or unreachable; any contradiction leads to review; evaluation (3 inflated fraud cases stopped) |
| 2 | Contradictions not covered deterministically; deterministic findings lost when Gemini failed | PAYMENT_ACCOUNT_CONFLICT (the same holder with different accounts, or one account with different holders). It is applied even when Gemini fails | Conflict, no-conflict and Gemini-failure tests; evaluation (2 cases) |
| 3 | Genuine applicants without formal quotations were stuck at NEEDS_MORE_INFORMATION | Assisted cost route; information requests list acceptable alternative evidence. All four checks still apply | Route only for cost-only gaps (not identity or need); assisted cases still need four checks, and an amount mismatch still leads to review |
| 4 | Date interpretation | Preserved: hybrid v3's event-aware model is reused unchanged | Scheduled future surgery is approved; a bill dated after submission is reviewed; an expired estimate leads to an information request |
| 5 | Gemini warnings | Preserved: a concern escalates only if its quote is found in the documents. Unquoted warnings are labelled UNVERIFIED_MODEL_SUSPICION. Gemini can never cause REJECTED, and a runtime assertion enforces this | Unquoted REJECT leads only to an unverified review referral; no REJECTED from Gemini on any fixture; quoted concerns carry their evidence |
| 6 | Explanations and audit | Every decision has an explanation, findings with a source label (V3_DETERMINISTIC, CROSS_DOCUMENT, DATE, PAYMENT_ACCOUNT, GEMINI_GROUNDED, GEMINI_UNVERIFIED) and document evidence, a case fingerprint, and the policy and settings versions. The audit log is hash-chained | Explanation test; tampering test; evaluation (60 of 60 chains valid) |

**Regression guard.** On the engineering fixtures, hybrid v4 makes exactly hybrid v3's decision unless a
payment-account conflict applies (tested under two different Gemini answers).

---

## 5. Problems discovered and fixed

**Earlier development (documented in earlier reports, all in-sample):**
- **Hybrid v3** fixed several V3 problems:
  - future *scheduled* events (surgery dates) read as future-dated documents;
  - years inside dates read as amounts;
  - approval without a valid cost document;
  - Gemini able to reject on its own;
  - unquoted Gemini suspicions escalating cases.
- **Its own development adjustments** are disclosed in `docs/hybrid_v3_safety_changes.md`, "Disclosed development
  adjustments".

**In this cycle:**

| Problem | Found by | Fix | Effect on evaluation numbers |
|---|---|---|---|
| The workflow refused the first transition because the decision entry was written to the audit log first | Smoke test on the engineering fixtures, before the evaluation | The "already started" check now looks for a state change | None (before the evaluation) |
| A document-quoted Gemini concern was missing from the explanation when a deterministic finding fired first | Unit test, after the first evaluation run | All Gemini concerns are listed with their source label | None |
| Future-date findings had no document reference | Inspection of evaluation explanations | The document and the date as written are attached | Evidence-referenced detections for hybrid v4: 22/25 in the first run, 23/25 after the fix. No decision changed |
| After the payment-conflict override, hybrid v3's "documents are consistent" reason was still shown | Demo output | The override reason replaces it; hybrid v3's decision is kept in separate fields | None |
| Payment-evidence quotes started mid-word | Demo output | Quotes start at the account-holder label | None |
| The approval reason listed three checks instead of four | Demo output | Wording | None |
| The 60 new scenarios were not in the v5 exclusion registry | Existing v5 test | Registered (43 sources, 4,023 texts), so they can never be reused as independent test data | None |

**No decision in the evaluation changed after the first run.** Every decision-level number in §6 is identical to the
first run.

**Problems found and *not* fixed**, because fixing them would mean tuning on the evaluation set or rewriting frozen code.
They are documented as limitations in §8.

---

## 6. Quantitative evaluation results

**Design.**
- **Scenarios:** 60 new synthetic scenarios (`evaluation/final_evaluation/scenarios.jsonl`, SHA-256 `f09a77af…eb6c`):
  15 detectable fraud (FD), 10 sophisticated or internally consistent fraud (FS), 15 legitimate complete (LC),
  10 legitimate incomplete (LI, 5 of them without a formal quotation), 10 borderline (BC). They cover medical,
  education and community campaigns.
- **Gemini script:** fixed before any run and identical for every system: 28 approve, 14 information request,
  10 quoted flags, 4 unquoted flags, and 4 failures (server error, read timeout, invalid JSON, truncated).
- **Same answer for every system:** each scripted answer passes through the frozen client's parser.
- **Systems:** frozen V3 alone, hybrid v2, hybrid v3 and hybrid v4.
- **Network:** a socket guard recorded 0 connection attempts and 0 API calls.

**Detection** means FLAG_FOR_REVIEW or REJECTED. **Activation** means VERIFIED_ACTIVE after the *simulated*
confirmations:
- the frozen systems use the frozen three-check workflow;
- hybrid v4 uses its four-check workflow and takes the assisted route where it offers one.

Percentages are of the stated denominators. With these sample sizes, 95% Wilson intervals are wide; examples follow
the main table.

| Measure | Frozen V3 | Hybrid v2 | Hybrid v3 | Hybrid v4 |
|---|---|---|---|---|
| Fraud detected, all fraud | 9/25 (36%) | 13/25 (52%) | 14/25 (56%) | 16/25 (64%) |
| Fraud detected, detectable from documents | 8/15 (53%) | 11/15 (73%) | 12/15 (80%) | 14/15 (93%) |
| Fraud detected, sophisticated | 1/10 (10%) | 2/10 (20%) | 2/10 (20%) | 2/10 (20%) |
| **Unsafe provisional approvals:** fraud | 14/25 (56%) | 8/25 (32%) | 8/25 (32%) | 7/25 (28%) |
| Unsafe provisional approvals: legitimate but incomplete | 7/10 (70%) | 1/10 (10%) | 0/10 (0%) | 0/10 (0%) |
| Unsafe provisional approvals: borderline | 5/10 (50%) | 2/10 (20%) | 1/10 (10%) | 1/10 (10%) |
| **Unsafe simulated activations:** fraud | 5/25 (20%) | 4/25 (16%) | 4/25 (16%) | **1/25 (4%)** |
| Fraud held before activation (any stage) | 20/25 (80%) | 21/25 (84%) | 21/25 (84%) | 24/25 (96%) |
| Borderline activated | 4/10 (40%) | 2/10 (20%) | 1/10 (10%) | 1/10 (10%) |
| Activations without independent amount confirmation | 30/30 (100%) | 17/17 (100%) | 17/17 (100%) | **0/19 (0%)** |
| **False positives:** all legitimate | 2/25 (8%) | 5/25 (20%) | 3/25 (12%) | 3/25 (12%) |
| False positives: legitimate complete | 1/15 (7%) | 3/15 (20%) | 1/15 (7%) | 1/15 (7%) |
| False positives: legitimate incomplete | 1/10 (10%) | 2/10 (20%) | 2/10 (20%) | 2/10 (20%) |
| **Legitimate approvals:** complete, provisional | 14/15 (93%) | 10/15 (67%) | 12/15 (80%) | 12/15 (80%) |
| Legitimate complete activated | 14/15 (93%) | 10/15 (67%) | 12/15 (80%) | 11/15 (73%) |
| Legitimate incomplete activated | 7/10 (70%) | 1/10 (10%) | 0/10 (0%) | 6/10 (60%) |
| Genuine without a formal quotation, activated | 4/5 (80%) | 1/5 (20%) | 0/5 (0%) | 4/5 (80%) |
| **Information requests:** all cases | 5/60 (8%) | 11/60 (18%) | 12/60 (20%) | 12/60 (20%) |
| Information requests: legitimate complete | 0/15 (0%) | 1/15 (7%) | 1/15 (7%) | 1/15 (7%) |
| Information requests: legitimate incomplete | 2/10 (20%) | 6/10 (60%) | 7/10 (70%) | 7/10 (70%) |
| **Manual reviews:** at the automated stage | 15/60 (25%) | 24/60 (40%) | 23/60 (38%) | 25/60 (42%) |
| Manual reviews: at the confirmation stage | 8 | 3 | 3 | 6 |
| Rejections | 0/60 | 0/60 | 0/60 | 0/60 |
| **Verification failures** (VERIFICATION_ERROR) | 0/60 (0%) | 4/60 (7%) | 4/60 (7%) | 3/60 (5%) |
| Assisted cost route taken | — | — | — | 7/60 (12%) |

**Decision explanations:**

| Measure | Frozen V3 | Hybrid v2 | Hybrid v3 | Hybrid v4 |
|---|---|---|---|---|
| Decisions with a stated reason | 60/60 | 60/60 | 60/60 | 60/60 |
| Detections with a recorded review basis | 0/15 | 0/24 | 23/23 | 25/25 |
| Detections citing document-level evidence | 15/15 | 0/24 | 3/23 | 23/25 |
| Tamper-evident audit record | 0/60 | 0/60 | 0/60 | 60/60 |

The 2 hybrid v4 detections without document evidence are unquoted Gemini suspicions. They are correctly labelled
UNVERIFIED_MODEL_SUSPICION, because they have no evidence.

**95% Wilson intervals, hybrid v3 against hybrid v4:**
- Fraud activated: 6.4–34.6% against 0.7–19.5%.
- Detectable fraud detected: 54.8–93.0% against 70.2–98.8%.
- False positives: 4.2–30.0% for both.

The intervals overlap. With 25 fraud cases, none of these differences is statistically established; the case-level
mechanism below is the stronger evidence.

**Where the numbers come from** (case IDs in `results/metrics.json`):
- **Fraud activations prevented by hybrid v4.** FE-FS-MED-02, FE-FS-EDU-02 and FE-FS-COM-02 have consistent but inflated
  estimates. They activated under hybrid v3 and stopped at the AMOUNT check under hybrid v4.
- **Fraud still activated by hybrid v4.** FE-FS-COM-03 is collusive: every independent party, including the supplier,
  confirms.
- **Extra detections by hybrid v4.** FE-FD-EDU-05 and FE-FD-COM-04 contain conflicting bank details. FE-FD-COM-04 is
  caught even though Gemini returned invalid JSON, which is also why hybrid v4 has one verification failure fewer.
  *Caveat:* the same developer wrote both the detector and these two scenarios, so these detections hold by
  construction.
- **Detectable fraud missed by hybrid v4.** FE-FD-MED-02 has documents belonging to a different patient. Every system
  asks for information (NEEDS_MORE_INFORMATION) and none approves it.
- **False positives** (identical for hybrid v3 and v4):
  - FE-LC-MED-05: an unquoted Gemini suspicion, labelled unverified;
  - FE-LI-EDU-02: date misread, see §8;
  - FE-LI-MED-04: reference number read as an amount, see §8.
- **Legitimate cost of the amount check.** In FE-LC-MED-04 the billing desk is unreachable, so the campaign stays
  pending under hybrid v4 but activated under hybrid v3.
- **Fairness gain.** Under hybrid v4, 6 of 10 legitimate incomplete cases (4 of the 5 without a formal quotation)
  activate via the assisted route after all four independent confirmations; hybrid v3 activated none. FE-LI-COM-01 is
  not offered the route, because frozen V3 also asks a non-cost clarification.

---

## 7. Before-and-after comparison

**This cycle: hybrid v3 (previous frozen candidate) against hybrid v4 (final), on the same 60 scenarios.**

| | Before (hybrid v3) | After (hybrid v4) | Change |
|---|---|---|---|
| Fraud activated (simulated) | 4/25 | 1/25 | −3 (all three were amount inflation) |
| Activations without independent amount confirmation | 17/17 | 0/19 | the amount is now always confirmed independently |
| Detectable fraud detected | 12/15 | 14/15 | +2 (payment-account conflicts) |
| Verification failures | 4 | 3 | −1 (deterministic finding despite Gemini failure) |
| False positives | 3/25 | 3/25 | unchanged |
| Legitimate complete activated | 12/15 | 11/15 | −1 (unreachable cost issuer) |
| Legitimate incomplete activated | 0/10 | 6/10 | +6 (assisted route) |
| Detections citing document evidence | 3/23 | 23/25 | explanations now cite evidence |
| Audit record | none | 60/60 hash chains valid | new |

**The project as a whole (in-sample context, not comparable to the table above):**
- **Development benchmarks.** On the 750 benchmark cases, the move from hybrid v2 to hybrid v3 reduced fraudulent
  provisional approvals from 64 to 20. It also reduced legitimate approvals from 231 to 162, and raised information
  requests from 336 to 460.
- **This evaluation.** Hybrid v4's assisted route addresses that fairness cost for applicants whose only gap is cost
  evidence.
- **Frozen V3 alone,** with no Gemini and no cost gate, approves the most legitimate cases. It also provisionally
  approves 56% of fraud cases and 70% of incomplete ones.

---

## 8. Remaining security limitations

| # | Limitation | Consequence |
|---|---|---|
| 1 | **Collusive or insider fraud.** When the institution, cost issuer or bank-account holder is complicit, every independent party confirms (FE-FS-COM-03) | Activation. No document- or contact-based design detects it. Payment straight to verified institutional accounts in tranches, plus post-disbursement audits, reduces the damage |
| 2 | **Confirmations are simulated.** No real KYC, bank-account verification or institution-contact process is connected | The workflow logic is tested; real-world feasibility, speed and accuracy are unknown |
| 3 | **Not wired into the application.** Production still uses `app/services/ai_verifier.py`, whose README-documented behaviour publishes a campaign as ACTIVE at a score of at least 80 | The live app does not yet have these safeguards |
| 4 | **The evaluation is developer-designed, small and uses scripted Gemini answers** | Optimistic in an unknown direction; wide intervals; Gemini's real behaviour and reliability are untested here (the last live free-tier run returned 1 valid answer in 4 requests) |
| 5 | **Two frozen-parser errors** caused false positives. FE-LI-MED-04: "Estimate AMH/26/3390" read as ₹3,390. FE-LI-EDU-02: in a one-line letter, the date in "Report by 25/09/2026" was taken as the issue date | Genuine applicants sent to review (never rejected). Not fixed, to avoid tuning on the evaluation set and editing frozen code |
| 6 | **Unquoted Gemini suspicions still create a manual review**, labelled UNVERIFIED_MODEL_SUSPICION (1 false positive; 1 sophisticated fraud caught this way) | A policy choice: downgrading them to information requests would cut false alarms but lose some referrals |
| 7 | **Documents of a different person** (FE-FD-MED-02) are not flagged; the case gets an information request | Not activated, but not referred for fraud review |
| 8 | **The audit log is tamper-evident, not tamper-proof.** It is held in memory, and an attacker who can rewrite every entry can rebuild the chain | Needs write-once storage, external anchoring of the chain head, and access control |
| 9 | **Thresholds are reasoned defaults, not calibrated:** 5% amount tolerance, date tolerances, traceability | Untested trade-offs |
| 10 | **Parsers were built on clean English text;** OCR, scans and regional languages are untested | Unknown behaviour on real uploads |
| 11 | **Retrieval in the evaluation** uses production's no-embedding fallback, not its embedding path | Ranking can differ for long dossiers |
| 12 | **The login test fails** (`tests/test_campaigns.py::test_campaign_verification_endpoint`): an authentication dependency was added on `main` and the test was never updated | Unrelated to verification; documented in `docs/known_issue_campaign_verification_test.md` |

---

## 9. Recommendations before production deployment

1. **Integrate hybrid v4 behind a feature flag:**
   - replace automatic activation with the four-check workflow;
   - persist workflow records and audit entries in write-once storage;
   - anchor the chain head externally;
   - build a reviewer and caseworker interface.
2. **Connect real confirmation channels:**
   - platform KYC;
   - penny-drop bank-account verification with name matching;
   - official directories (for example NMC or state councils, NABH, UDISE+ or AISHE, NGO Darpan or registrars);
   - a documented cost-issuer confirmation procedure run by trained caseworkers.
3. **Pay institutions directly, in invoice-backed tranches,** to limit collusive and insider fraud.
4. **Validate independently before any claim of effectiveness.** The preserved v5 protocol and tooling
   (`evaluation/independent_test_protocol_v5.md`) are ready for this. Run an authorised live Gemini pilot to measure
   real reliability.
5. **Fix the known parser errors in a new version, tested on new data:**
   - identifiers read as amounts;
   - unlabelled dates in one-line documents.

   Also decide the policy for unquoted model suspicions.
6. **Before launch:**
   - security review;
   - data-protection review (Digital Personal Data Protection Act 2023): beneficiary documents, consent and retention;
   - monitoring of fairness metrics across categories, hospital types and regions;
   - fix the login test.

---

## 10. Final conclusion

The development prototype is complete. Its central safety property, no activation without independent confirmation
of beneficiary, institution, payment destination and amount, is implemented, unit-tested and exercised end to end with
simulated confirmations.

On 60 developer-designed scenarios, hybrid v4:
- reduced simulated fraud activations from 4 to 1 compared with the previous candidate;
- independently confirmed the amount for every activation;
- kept false positives unchanged;
- let 4 of 5 genuine applicants without formal quotations reach activation safely, against none before;
- cost one genuine campaign a delay, because its billing desk could not be reached.

These results come from a developer-designed synthetic evaluation, not from independent validation. The remaining
critical issues are collusive fraud, simulated rather than real confirmations, and the lack of integration with the
live application. The prototype is ready for a local demonstration, not for production.

---

**Reproducibility**:
- `python evaluation/final_evaluation/run_final_evaluation.py` regenerates `evaluation/final_evaluation/results/`
  exactly; the test `test_final_evaluation_reproduces_its_committed_metrics` checks this.
- **Freezes:** `python evaluation/freeze_hybrid_v3.py verify` (which also verifies hybrid v2 and frozen V3) returns
  `valid: true`.
- **Benchmarks:** `python evaluation/check_frozen_benchmark_reproducibility.py` returns `all_reproduced: true`.
- **Tests:** 513 passed, 1 failed (the documented login test).
