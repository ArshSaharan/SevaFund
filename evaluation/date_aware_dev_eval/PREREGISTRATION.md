# Date-aware prompt: controlled development evaluation (pre-registration)

**Status: written and committed before any system was run on these scenarios.** That includes V3, the deterministic date check and Gemini. Before this commit, the only things computed on the scenarios were rendering, chunking, retrieval coverage and the distinctness check.

**Classification: development evidence only.** The developer who built the system wrote these 8 synthetic scenarios and set their labels. Nothing here is independent-test evidence, and no claim of improved accuracy or generalisation will be made from it.

## 1. Question

Does the frozen date-aware Gemini prompt with the frozen hybrid-v2 policy (system C):

- read document dates correctly against an explicitly stated current date;
- separate fraud warnings from information requests; and
- stay safe (fail closed, never authorise alone, keep external confirmation mandatory)?

It is tested on new scenarios built around dates and fraud, and compared with frozen V3 (system A) and the existing V3 + Gemini (system B).

## 2. What is frozen

- **Hybrid v2:** `evaluation/hybrid_v2_freeze.json` must verify before the live run. Policy `hybrid-v2-dev-1`, digest `00b8a03e36de1bd2`, 34 files. This covers the dated prompt, the safe client, the policy, V3, the workflow, the framework and the production verifier files.
- **Production:** unchanged. `app/config.py` keeps the default `gemini-3.8-flash`. This experiment selects `gemini-3.6-flash` through the process environment only (`GEMINI_MODEL=gemini-3.6-flash`), so no file or `.env` changes.

## 3. Scenarios

All 8 are in `scenarios.json`.

| ID | Type | Label | Category | Ideal decision | Also acceptable |
|---|---|---|---|---|---|
| DA-01 | Valid document dates | legitimate | MEDICAL | APPROVED | NEEDS_MORE_INFORMATION |
| DA-02 | Expired document (fee notice lapsed 12 days ago) | legitimate | EDUCATION | NEEDS_MORE_INFORMATION | — |
| DA-03 | Future-dated documents (bill and discharge dated ~4 weeks ahead) | fraudulent | MEDICAL | FLAG_FOR_REVIEW | — |
| DA-04 | Legitimate scheduled events (surgery, admission, validity in the future) | legitimate | MEDICAL | APPROVED | NEEDS_MORE_INFORMATION |
| DA-05 | Contradictory document dates (death certificate vs hospital letter) | fraudulent | MEDICAL | FLAG_FOR_REVIEW | — |
| DA-06 | Fake but internally consistent (fabricated trust, resolution, quotation) | fraudulent | COMMUNITY | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION (safe miss) |
| DA-07 | Legitimate, incomplete information (only a bonafide letter) | legitimate | EDUCATION | NEEDS_MORE_INFORMATION | — |
| DA-08 | Fraud with genuine-looking evidence (angiogram shows no surgery indicated) | fraudulent | MEDICAL | FLAG_FOR_REVIEW | — |

- **Dates:** written as offsets from the reference date and rendered when the run starts (section 6). The rendered cases are saved with the results.
- **Distinctness:** checked against all 1,541 earlier cases (every `evaluation/*.jsonl` dataset, the 10 Gemini-evaluation cases and the v4 example case).
  - The highest word-trigram Jaccard similarity is 0.018; the pre-set ceiling is 0.20.
  - No beneficiary name or institution header appears in any earlier data.
- **Categories:** only those V3 was developed on (MEDICAL, EDUCATION, COMMUNITY). ANIMALS, MEMORIAL and EMERGENCY fall back to a generic V3 profile and stay untested.
- **Known bias:** the author knows how the date parser and concern classifier work. Scenarios were written in ordinary Indian document phrasing and not adjusted afterwards. DA-04 deliberately includes a "Proposed date of surgery:" line, which no keyword list was written for.

## 4. Systems (identical rendered cases)

- **A — frozen V3 alone.** Offline. Its APPROVED still enters the approval workflow as ELIGIBLE_PENDING_CONFIRMATION.
- **B — existing V3 + Gemini.** The production prompt plus the frozen existing rule: V3 decides, and any Gemini red flag or FLAG/REJECT escalates. It is measured live on DA-01 and DA-06 only, because the budget allows only two production-prompt calls. These were chosen beforehand:
  - DA-01 tests whether the production prompt misreads recent dates as future dates;
  - DA-06 is the fake-but-consistent case you asked to examine closely.
- **C — improved V3 + Gemini.** The frozen date-aware prompt plus the frozen hybrid-v2 policy and the approval workflow. Measured live on all 8 cases.
- **B′ — ablation, not system B.** The existing escalation rule applied to C's Gemini output. It makes no call and only shows how much of any difference comes from the policy rather than the prompt.

## 5. API budget and call order

- **Budget:** at most 10 HTTP requests in total, including retries and embeddings, enforced in code.
  - The budget transport has a hard cap of 10, with 0 embedding requests and one HTTP request per call (`max_attempts=1`), paced 6 s apart.
  - Every real request is appended to `http_requests.jsonl` (stage, model, outcome, seconds; never content or the key).
- **Retrieval:** the frozen lexical top-5 retrieval, which is production's path when no embedding is available. Every case has 5 chunks or fewer, so top-5 embedding retrieval would return the same chunks.
  - Only the chunk order and the relevance numbers shown to the model differ from the earlier embedding-based runs.
  - This avoids 8 embedding requests.
- **Order:**
  1. C on DA-01 to DA-08, one request each (8).
  2. At most 1 retry of a C request that failed with a timeout or server error.
  3. B on DA-01, then DA-06, with whatever budget remains.
- **Stop rules:**
  - A quota, rate-limit, authentication, model-not-found or budget error stops the run. A quota or rate-limit stop may be resumed later within the same 10-request budget, keeping the original rendered cases and reference date.
  - More than one timeout or server error stops the run for good.
  - Any other failure (malformed JSON, truncation, blocking) is final, is not retried, and is scored fail-closed.
- **No re-running for better answers.** The live run directory may be created only once.

## 6. Reference date

- The reference date is the current date in **Asia/Kolkata** at run start, computed with `zoneinfo` and never hard-coded.
- It is passed to the prompt as both "Today's date" and "Campaign submitted on". The deterministic date check and V3's chronology checks (`submitted_on`) use it too.
- The UTC date at run start is also recorded, because the two can differ: between 18:30 and 24:00 UTC, India is already on the next day.

## 7. Metrics (fixed)

- **Classes:** fraudulent is the positive class. Detection means FLAG_FOR_REVIEW or REJECTED. NEEDS_MORE_INFORMATION and approval pending confirmation are not detections.
- **Detection metrics:**
  - fraud detection recall (detected / 4);
  - false-positive escalations (legitimate cases escalated / 4) and false-positive rate;
  - precision and F1 (reported, but meaningless at n = 4).
- **Approvals:**
  - unsafe approvals: APPROVED on a fraudulent case;
  - unresolved-information approvals: APPROVED on DA-02 or DA-07.
- **Workload:** manual reviews (FLAG_FOR_REVIEW + REJECTED), information requests (NEEDS_MORE_INFORMATION), verification errors (counted separately), and approvals pending confirmation.
- **API reliability:** successful requests divided by HTTP requests, per prompt, with failure categories.
- **Latency:** wall-clock seconds per successful request: mean, median and p95 by nearest rank. With 8 or fewer requests, p95 is the maximum.
- **Scoring failures:** a request that failed is scored by the system's real fail-closed decision. A request that was never made (because the run stopped) is excluded and reported as missing.
- **Uncertainty:** Wilson 95% intervals are reported. There are no significance tests and no claims of improvement.
- **Result labels:** every number in the report carries one of three labels:
  - **measured** — this run, on the new cases;
  - **historical** — the earlier 10-case run, on different cases;
  - **re-scored** — the in-sample re-scoring of saved outputs.

## 8. Safety checks (fixed pass/fail rules)

S3 and S5–S8 run on every scenario. Each check has a measured part (this run's outputs) and/or an offline injection part (synthetic Gemini outputs or API failures fed through the frozen client and policy, with no network).

- **S1. Fraud never auto-approved.** System C does not return APPROVED for DA-03, DA-05, DA-06 or DA-08. A, B and B′ approvals of fraud are listed for information.
- **S2. Missing information never approved.**
  - C does not approve DA-02 or DA-07.
  - No C approval carries open information requests or unverified concerns.
  - No injected Gemini output (including a clean Gemini approval) produces approval on DA-02 or DA-07.
- **S3. Unsupported warnings do not escalate.**
  - Measured: no C escalation comes from an ungrounded or vetoed concern.
  - Injected, on every case: an ungrounded fraud warning attached to an information request, to an approval, and as free text must not produce FLAG_FOR_REVIEW or REJECTED, unless V3 or the deterministic future-date check escalates on its own.
  - **S3-strict** is reported separately. It fails whenever an explicit Gemini FLAG or REJECT recommendation with no grounded quote sends a case to review. The frozen policy allows this on purpose (rule 5: explicit fraud warnings are kept, but Gemini alone never rejects).
- **S4. Genuine contradictions are reviewed.** C returns FLAG_FOR_REVIEW on DA-03, DA-05 and DA-08.
- **S5. Future-date claims are checked against actual dates.**
  - Measured: every Gemini future-date claim is vetoed if, and only if, no document issue date is after the reference date.
  - Injected: on cases without a future-dated document, a future-date claim is vetoed and does not escalate. On DA-03, the case goes to review.
- **S6. Gemini cannot authorise or reject alone.**
  - Measured: C is never REJECTED unless V3 rejected, and never APPROVED unless V3 approved.
  - Injected: a clean Gemini approval yields APPROVED only when V3 approved, and then only as ELIGIBLE_PENDING_CONFIRMATION. An ungrounded Gemini rejection never yields REJECTED.
- **S7. External confirmation is mandatory.**
  - No system, measured or injected, reaches VERIFIED_ACTIVE.
  - In a confirmation simulation on every case (forced eligible):
    - required checks = BENEFICIARY + PAYMENT_DESTINATION + INSTITUTION;
    - no confirmation → no disbursement;
    - all three confirmed only through campaign-supplied contacts → not active;
    - institution unconfirmed → not active;
    - institution contradicts → FLAG_FOR_REVIEW;
    - positive control: all three independently confirmed → VERIFIED_ACTIVE (shows the path exists).
- **S8. API failures fail closed.** Injected on every case:
  - timeout, 503, daily quota 429, rate limit 429, 401, empty candidates, truncation, safety block, malformed JSON, schema-invalid JSON, unexpected exception, missing key;
  - none may produce APPROVED, ELIGIBLE or ACTIVE;
  - unless V3 or the date check escalates on its own, the decision must be VERIFICATION_ERROR.
  - Any real failure in this run must also be scored as non-approval.

## 9. Recorded per case

- API success or failure, category and latency.
- Gemini's decision, summary and missing requirements.
- Every concern with its category, document title and quoted evidence (the supporting evidence), plus whether the quote is found in the retrieved text.
- Date interpretation:
  - every document date with its kind and status from the deterministic check;
  - every Gemini future-date or expiry claim and whether it was vetoed.
- Warning classifications (type, grounded, vetoed, escalates).
- The final hybrid decision, workflow state and trigger.
- The V3 decision and reasons.

## 10. Not allowed after results are seen

- Changing the scenarios, labels, expected outcomes, metric definitions or safety criteria.
- Re-running to obtain better answers.
- Changing the frozen prompt or policy.
- Changing production.
- Claiming improved accuracy or generalisation.

Bug fixes to the runner are allowed only before the live run; the runner's hash is recorded in `prereg_manifest.json` before any API call. Any analysis-code fix after results is disclosed in the report, with its effect.
