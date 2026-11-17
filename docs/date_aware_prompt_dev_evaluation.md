# Date-aware Gemini prompt: controlled development evaluation

**Status: finished, but incomplete by design.** The run stopped under its pre-registered early-stop rule after 4 of the 10 approved API requests:

| Request | Case | Outcome |
|---|---|---|
| 1 | DA-01 | 503 server error |
| 2 | DA-02 | Success |
| 3 | DA-03 | Daily quota exhausted |
| 4 | DA-03 | 503 server error |

The other 6 requests were never sent, and no more work is scheduled.

What exists:

- **one** real Gemini answer from the date-aware prompt (DA-02);
- two fail-closed API failures (DA-01, DA-03);
- frozen V3 run offline on all 8 cases;
- offline injection tests of the frozen policy on all 8 cases.

**Classification: development evidence only.** The 8 scenarios were written and labelled by the developer of the system. Nothing here is independent-test evidence. None of it supports a claim of improved accuracy or generalisation.

Run artefacts: `evaluation/runs/date_aware_dev_eval_live/`. Protocol: `evaluation/date_aware_dev_eval/PREREGISTRATION.md`.

---

## 1. Experimental methodology

**Pre-registration**

- **Commit `978df4d`, before any system ran on them:** the scenarios, labels, expected outcomes, metric definitions and safety-check rules. Before that commit, the only things computed on the scenarios were rendering, chunking, retrieval coverage and a distinctness check.
- **Commit `baf3e4e`, before any API call:** the runner, its tests and `prereg_manifest.json` (SHA-256 of all four files). The runner refuses to call the API unless those hashes match committed files.
- **One clarification after `978df4d`, still before any API call:** latency is defined as time inside the HTTP request, excluding the 6 s pacing between requests.
- **No change after results were seen.** The scenarios, labels, metrics and criteria are as registered. The analysis code is unchanged.

**What was frozen**

- **Hybrid v2:** `evaluation/hybrid_v2_freeze.json` verified before and after the run. Policy `hybrid-v2-dev-1`, digest `00b8a03e36de1bd2`, 34 files.
- **Production:** unchanged. The default model in `app/config.py` is still `gemini-3.8-flash`. The run selected `gemini-3.6-flash` only through the environment of its own process.

**Systems, on identical rendered cases**

| | System | How it was run |
|---|---|---|
| A | Frozen V3 alone | Offline, all 8 cases. Its APPROVED enters the workflow as ELIGIBLE_PENDING_CONFIRMATION. |
| B | Existing V3 + Gemini: production prompt + frozen existing rule (any Gemini red flag escalates) | Planned live on DA-01 and DA-06 with leftover budget. **Never run** (see §5.1). |
| C | Improved V3 + Gemini: frozen date-aware prompt + frozen hybrid-v2 policy + approval workflow | Live, planned on all 8 cases. Obtained: 1 answer and 2 failures. |
| B′ | Ablation, *not* B: the existing escalation rule applied to C's Gemini output | No call. 1 case. |

**Reference date**

- The reference date is the current date in Asia/Kolkata at run start, computed with `zoneinfo`: **2026-11-17**.
- The UTC date at that moment was still 2026-11-16, because the run started at 20:26 UTC. A UTC-based date would have been a day early.
- The date is passed to the prompt as both "Today's date" and "Campaign submitted on". The deterministic date check and V3's `submitted_on` use it too.
- The resumed request (08:10 UTC on 17 November, 13:40 IST) used the same rendered cases and reference date.

**Retrieval**

- The frozen lexical top-5 retrieval was used, which is production's path when no embedding is available.
- Every case has 5 chunks or fewer, so top-5 embedding retrieval would return the same chunks; only their order and relevance numbers differ.
- No embedding requests were made.

**API controls**

- A budget transport with a hard cap of 10 HTTP requests and 0 embeddings.
- One HTTP request per call (`max_attempts=1`), with 6 s pacing.
- Every real request is logged in `http_requests.jsonl` (stage, model, outcome, seconds; never content or the key).

**Stop rules (pre-registered)**

- A quota or rate-limit error stops the run; it may be resumed within the same budget.
- More than one timeout or server error stops the run for good.
- One timeout or server error may be retried once.

**Scoring**

- A failed request is scored by the system's real fail-closed decision.
- A request that was never sent is excluded and reported as missing.

## 2. Test scenarios

The 8 scenarios are new and written by the developer. They were compared with all 1,541 earlier cases:

- the highest word-trigram Jaccard similarity is 0.018, against a ceiling of 0.20;
- no beneficiary name or institution header repeats.

Only the categories V3 was developed on (MEDICAL, EDUCATION, COMMUNITY) are used.

| ID | Scenario type | Label | What it tests |
|---|---|---|---|
| DA-01 | Valid document dates | legitimate | Hip-fracture bill. All dates 9–19 days in the past; amounts reconcile exactly. |
| DA-02 | Expired document | legitimate | Veterinary college fee notice "valid until" 12 days ago, which itself says a revised notice is needed. |
| DA-03 | Future-dated documents | fraudulent | Final bill and discharge summary dated 26–27 days *after* today, for a discharge the story says happened 6 days ago. |
| DA-04 | Legitimate scheduled events | legitimate | Cleft-palate repair. Letter issued 9 days ago; surgery, pre-anaesthetic check and admission in the future. |
| DA-05 | Contradictory document dates | fraudulent | Hospital letter says death in the ICU 3 days ago; the municipal death certificate records death at home 209 days ago. |
| DA-06 | Fake but internally consistent | fraudulent | Fabricated animal-rescue trust: registration, board resolution and quotation all agree. Only a registry check would reveal it. |
| DA-07 | Legitimate, incomplete | legitimate | Braille textbooks. Only a school bonafide letter; the story says the supplier quotation is still being collected. |
| DA-08 | Fraud with genuine-looking evidence | fraudulent | The angiogram says no surgery is indicated and the only bill (₹26,800) is paid; the campaign asks ₹5,60,000 for "urgent bypass". |

## 3. Per-case predictions

**Measured** means V3 run offline, or the live API request. **Missing** means the request was never sent.

| ID | Label | A: V3 | C: Gemini (live) | C: final decision | C: workflow state | C: trigger | B | B′ |
|---|---|---|---|---|---|---|---|---|
| DA-01 | legit | APPROVED | **503 SERVER_ERROR** (0.82 s) | VERIFICATION_ERROR | VERIFICATION_ERROR | GEMINI_FAILED:SERVER_ERROR | not run | — |
| DA-02 | legit | APPROVED | NEEDS_MORE_INFORMATION (27.7 s) | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | EXPIRED_DOCUMENT | not run | **APPROVED** |
| DA-03 | fraud | FLAG_FOR_REVIEW | **503 SERVER_ERROR** (0.80 s; an earlier attempt hit the quota) | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | V3_CONTRADICTION | not run | — |
| DA-04 | legit | **FLAG_FOR_REVIEW** (false positive) | missing | — | — | — | not run | — |
| DA-05 | fraud | **APPROVED** | missing | — | — | — | not run | — |
| DA-06 | fraud | **APPROVED** | missing | — | — | — | not run | — |
| DA-07 | legit | **APPROVED** | missing | — | — | — | not run | — |
| DA-08 | fraud | FLAG_FOR_REVIEW | missing | — | — | — | not run | — |

### DA-02 in full: the only real Gemini answer

**API:** success. 27.7 s inside the HTTP request. `per_case.csv` shows 32.9 s, which includes the 5.2 s pacing wait.

**Gemini decision:** NEEDS_MORE_INFORMATION, risk LOW.

Summary, verbatim:

> "The campaign is highly credible and backed by verifiable institutional documents including a bonafide student certificate and tehsildar-issued income certificate. However, the fee demand notice expired on 05/11/2026 prior to the campaign submission date, so an updated notice from the accounts office is required to confirm final payable fees."

**Supporting evidence:**

- **Concern category:** DATE_ISSUE on "Fee demand notice".
- **Quote:** *"This notice is valid until 05/11/2026. After that date late-fee rules apply and a revised notice must be obtained from the accounts office."*
- **Grounding:** the quote was found in the retrieved text, so the concern is grounded.

**Missing requirement listed by Gemini:**

> "Revised fee demand notice from the college accounts office reflecting current status and potential late fees."

**Date interpretation:**

- *Gemini:* correct. It compared 05/11/2026 against the stated submission date of 17/11/2026, and made no future-date claim.
- *Deterministic check:*
  - fee notice issued 20/09/2026 → VALID;
  - "valid until" 05/11/2026 → **EXPIRED**;
  - bonafide certificate 27/10/2026 → VALID;
  - income certificate 30 June 2026 → VALID.
- Gemini and the deterministic check agree.

**Warning classification:** one DATE_CLAIM (an expiry, not a future-date claim). It is grounded, not vetoed, and does not escalate. No fraud warning was raised.

**Final hybrid decision:**

- NEEDS_MORE_INFORMATION, triggered by `EXPIRED_DOCUMENT` (the deterministic rule 7).
- Information request: "Provide a current version of 'Fee demand notice'."
- This matches the pre-registered ideal outcome.

**Contrast:**

- V3 alone approved DA-02.
- The **existing escalation rule (B′), applied to this same Gemini output, also returns APPROVED.** It escalates only on red flags or FLAG/REJECT, and ignores a Gemini information request.

### Date interpretation on every case (deterministic check, offline)

| ID | Document dates → status | Future-dated | Expired |
|---|---|---|---|
| DA-01 | Issue dates 08/11 and 29/10 VALID; admission, surgery and advance dates MENTIONED | — | — |
| DA-02 | See above | — | Fee demand notice |
| DA-03 | Admission record 02/11 VALID; **Final bill 14/12/2026 FUTURE; Discharge summary 13/12/2026 FUTURE** | Final bill, Discharge summary | — |
| DA-04 | Letter 08/11 VALID; "Proposed date of surgery 05/12", "check on 28/11", "admission on 04/12" MENTIONED; estimate valid until 07/01/2027 VALID | — | — |
| DA-05 | Release letter 15/11 VALID; death certificate 25/04 VALID; date of death 22/04 MENTIONED | — | — |
| DA-06 | 21/01, 24/10 and 28/10 VALID | — | — |
| DA-07 | 03/11 VALID | — | — |
| DA-08 | 25/10 VALID | — | — |

The deterministic check classified every case as intended, including the scheduled events in DA-04. **Frozen V3's own date logic did not** (see §5.3).

## 4. Comparison tables

The four tables are kept separate on purpose. They cover different cases, different prompts or different kinds of evidence, so **their numbers must not be compared as if they were one experiment.**

### 4.1 Live measurement on the new cases

Systems A and B′ use no API. System C contributes 1 Gemini answer and 2 failures.

| Metric | A: frozen V3 (8 cases) | B: existing V3 + Gemini | C: improved V3 + Gemini (3 cases scored) | B′: ablation (1 case) |
|---|---|---|---|---|
| Fraud detection recall | 2/4 (Wilson 95% 0.15–0.85) | **not measured** | 1/1 (0.21–1.00). DA-03 was caught by V3; Gemini failed on it. | no fraud case |
| False-positive escalations | 1/4: DA-04 (0.05–0.70) | not measured | 0/2 (0.00–0.66) | 0/1 |
| Unsafe approvals (fraud APPROVED) | **2: DA-05, DA-06** | not measured | 0 | 0 |
| Approvals with unresolved information | **2: DA-02, DA-07** | not measured | 0 | **1: DA-02** |
| Manual reviews (FLAG + REJECT) | 3 | not measured | 1 | 0 |
| Information requests | 0 | not measured | 1 | 0 |
| Verification errors | 0 | not measured | 1 | 0 |
| Approved, pending confirmation | 5 | not measured | 0 | 1 |
| API reliability | n/a (offline) | 0 requests | **1/4 succeeded**: 2 × 503 SERVER_ERROR, 1 × QUOTA_EXHAUSTED | n/a |
| Latency, mean / p95 | ~ms (offline) | — | 27.7 s / 27.7 s (n = 1) | n/a |

The analysis prints F1 = 0.0 for B′. B′ has no fraud case, so F1 is undefined. This is a quirk of the analysis code, which is unchanged.

### 4.2 Gemini-independent outcomes for system C (offline, not live measurements)

On DA-03, DA-04 and DA-08, V3 already returns FLAG_FOR_REVIEW. Policy rule 2 applies V3's contradictions before anything Gemini returns. The offline injections confirm that C's decision on these cases is FLAG_FOR_REVIEW for **every** Gemini output and every API failure. These outcomes are therefore known without a live call:

| ID | Label | C decision for any Gemini output | Meaning |
|---|---|---|---|
| DA-03 | fraud | FLAG_FOR_REVIEW | Detected (by V3's future-date check) |
| DA-04 | legit | **FLAG_FOR_REVIEW** | **Certain false positive**, inherited from V3 |
| DA-08 | fraud | FLAG_FOR_REVIEW | Detected (V3: already settled; amount 20.9× the documented cost) |

On DA-05, DA-06 and DA-07, C's decision depends entirely on Gemini, which was not measured. See §5.5 for what each possible Gemini output would produce.

### 4.3 Historical: the earlier 10-case run (different cases, production prompt)

Source: `evaluation/runs/gemini_eval_v1_3_6`, measured on 2026-11-16 with gemini-3.6-flash. Negatives were 6 non-fraud cases (legitimate and borderline).

| Metric | Original V3 | Existing V3 + Gemini |
|---|---|---|
| Fraud detection recall | 2/4 | 4/4 |
| False-positive escalations | 0/6 | 4/6 |
| Unsafe approvals | 3 | 0 |
| Manual reviews | 2 | 8 |
| Information requests | 2 | 0 |
| Verification errors | 0 | 1 |
| API reliability | — | 19/20 (1 × 503) |
| Latency, mean / p95 | — | 45.5 s / 72.5 s |

### 4.4 Re-scored in-sample: the improved policy on those same saved outputs

Source: `evaluation/runs/hybrid_policy_rescoring_20261116T160320Z`.

- **Results:** recall 3/4, false-positive escalations 0/6, unsafe approvals 0, manual reviews 3, information requests 5, verification errors 1.
- **Why this is not evidence of improvement:** the policy was designed after looking at these outputs, and they come from the *production* prompt, not the date-aware one.
- **Reproduction:** confirmed again today, with all 10 decisions identical (§9).

### 4.5 What can and cannot be concluded

**Can be concluded**

- On DA-02 (one case), the date-aware prompt read an expiry correctly against the stated date, quoted the evidence and asked for information instead of alleging fraud.
- The hybrid-v2 policy turned that into the intended information request.
- Applied to the same output, the old escalation rule would have approved the case.

**Cannot be concluded**

- Anything about recall, false-positive rate, the prompt's effect on future-date misreading (DA-01, DA-03 and DA-04 never got an answer), or how B compares with C on new cases.
- That the improved system is more accurate.

## 5. Failure analysis

### 5.1 Why the run is incomplete

- **20:26 UTC, 16 November (run started on request).** At my last update the free-tier quota had been reported as exhausted, and the run was scheduled for after the 08:00 UTC reset. When you replied "continue", I started it immediately instead. Results:
  - Request 1 (DA-01) got a 503 after 0.82 s.
  - Request 2 (DA-02) succeeded. It was evidently the last request left in the daily quota, since the next request was refused.
  - Request 3 (DA-03) got QUOTA_EXHAUSTED, a resumable stop.
- **08:10 UTC, 17 November (resumed).** Request 4 (DA-03 again) got a 503 after 0.80 s. That was the second server error, so the pre-registered rule stopped the run for good, with 6 requests unused.
- **Cost of starting early:**
  - one request went to a quota error;
  - the DA-01 retry would have had to come out of the two production-prompt slots;
  - system B was never run, so there is no live B-versus-C comparison.
- **The 503s:**
  - Both were returned in under a second, so they look like capacity rejections rather than timeouts.
  - The second came within seconds of the daily quota reset.
  - That points to transient load on the free tier, but this is a hypothesis; the response bodies were deliberately not logged.
- **Reliability in context:**
  - Across both runs on gemini-3.6-flash, 3 of 23 non-quota *generation* requests returned 503 (1/20 historically, 2/3 today).
  - This is descriptive only: the two runs used different days, prompts and cases.
- **Was the early-stop rule too strict for a 10-request budget?** Possibly. It mirrors the earlier instruction ("stop … if more than one generation call fails because of a timeout or server error") and was pre-registered, so it was followed. Finishing would need a new, separately approved run (§8).

### 5.2 Failed safety test S2: missing information can be approved

**What failed (offline injection, DA-07):**

| Injected Gemini output | C decision |
|---|---|
| Clean approval | **APPROVED** (BOTH_APPROVE → ELIGIBLE_PENDING_CONFIRMATION) |
| Approval with a future-date claim (vetoed) | **APPROVED** |
| Approval with an ungrounded warning | NEEDS_MORE_INFORMATION (correct) |

DA-07 has no cost document, and its story says the quotation is still being collected.

**Root cause (frozen V3):**

- V3's EDUCATION requirements for an individual are:
  - `critical_claim_support` (critical) and `beneficiary_identity` (critical), both satisfied by the school bonafide letter;
  - `cost_traceability`, which is **non-critical**;
  - `enrolment_detail`, non-critical.
- So V3 returns APPROVED with "Optional supporting records are incomplete; this did not block approval."
- The hybrid-v2 policy approves when V3 and Gemini both approve and nothing is unresolved. It has no completeness requirement of its own, and it does not read "still collecting the quotation" in the story as an open item.
- The only remaining barrier is Gemini choosing to ask for the quotation. Its live behaviour on DA-07 was not measured.

**Impact:**

- A legitimate but unevidenced amount (₹38,500 here) could reach ELIGIBLE_PENDING_CONFIRMATION.
- It still cannot be disbursed without three independent confirmations (S7 passed). But the institution confirmation (the school) would confirm enrolment, not the amount, so **the amount itself would never be independently verified.**

**Verdict:** a genuine gap, not a test artefact. S2 is recorded as **FAIL**, as pre-registered.

### 5.3 Date-handling failure in frozen V3 (DA-04 false positive)

**Root cause:**

- The surgeon's letter has the line "Proposed date of surgery: 05/12/2026".
- V3's extractor gives a date the *issue* role when the nearby text matches `\bdate\b`. So it records 05/12/2026 as the letter's **issue date**.
- That raises `FUTURE_DATED_DOCUMENT` (MATERIAL severity, confidence 0.85): "'Surgeon's letter' records an issue date after the campaign was submitted."
- V3 also raises an uncertain `SERVICE_UNRELATED` finding (confidence 0.4), because its lexicon does not link "palatoplasty" to "cleft palate repair". This does not decide the outcome.

**Why the improved system does not fix it:**

- The hybrid-v2 date check classifies the same date correctly, as MENTIONED.
- But its veto applies only to *Gemini's* date claims. V3's contradictions are applied first (rule 2).
- So **C would flag DA-04 for any Gemini output**. That is a certain false positive on exactly the "legitimate scheduled event" case this work was meant to protect.
- This was not seen earlier because no development case phrased a future event with the word "date".

**Mitigating factor:** it fails safe. The case goes to a reviewer, not to rejection.

### 5.4 Failed safety test S3-strict: an ungrounded Gemini recommendation reaches manual review

**What failed (injected):**

- An explicit Gemini FLAG_FOR_REVIEW or REJECTED, with no quotable evidence, sends DA-01, DA-02, DA-05, DA-06 and DA-07 to FLAG_FOR_REVIEW via `GEMINI_EXPLICIT_FRAUD_WARNING`.
- These are the cases where V3 does not already flag.
- On DA-02, this rule also comes before the expired-document rule.

**Root cause:** this is by design (policy rule 5). The previous instruction was to keep explicit fraud warnings. Gemini still cannot reject: an injected REJECTED becomes FLAG_FOR_REVIEW, and S6 passed.

**Impact:** no unsafe approval. It can create model-only reviews and false positives on legitimate campaigns, since Gemini's word alone is enough to send a legitimate campaign to a reviewer.

**S3 proper passes:** ungrounded *warnings* attached to an information request or an approval, and free-text warnings, never escalated on any case.

### 5.5 Cases that could be approved with unresolved evidence

The offline injections, through the frozen client and policy, show which Gemini outputs would lead to APPROVED for each case. Every approval enters ELIGIBLE_PENDING_CONFIRMATION; none can reach VERIFIED_ACTIVE.

| ID | Label | System C approves if Gemini… | What is still unresolved at that point |
|---|---|---|---|
| **DA-05** | fraud | approves cleanly, or approves with only a (vetoed) future-date claim | The death certificate (death at home 209 days ago) contradicts the hospital letter (ICU, 3 days ago). V3 has no rule comparing dates of death, so detection depends **only** on Gemini noticing. |
| **DA-06** | fraud | approves cleanly | Everything: the trust, resolution and quotation are fabricated but consistent. As pre-registered, only external confirmation can stop this. |
| **DA-07** | legit | approves cleanly, or with a vetoed date claim | No cost document; the quotation is still pending (§5.2). |
| DA-01 | legit | approves cleanly | Nothing. This approval would be correct. |
| DA-02 | legit | never (expired-document rule) | — |
| DA-03, DA-04, DA-08 | — | never (V3 flags) | — |

Other systems:

- **A (V3 alone)** approves DA-02 (expired notice), DA-05, DA-06 and DA-07 without any Gemini involvement.
- **The existing escalation rule** approved DA-02 on a real Gemini answer (B′).

**DA-06, the fake-but-consistent case.** This is the case that needs independent institutional confirmation. The confirmation simulation, with the case forced to eligible, gave:

| Simulated confirmations | Outcome |
|---|---|
| None | Disbursement not allowed |
| All three checks confirmed only through campaign-supplied contacts | Stays ELIGIBLE_PENDING_CONFIRMATION |
| Beneficiary and payment confirmed, institution not | Stays pending |
| Institution contradicts the claim | FLAG_FOR_REVIEW |
| All three independently confirmed (positive control) | VERIFIED_ACTIVE |

So the control is correctly *wired*. Whether a real registry or dealer check would catch a fabricated trust has **not been measured**; the confirmation pilot protocol exists but has not been run.

### 5.6 Safety checks: full results

| Check | Result | Basis |
|---|---|---|
| S1 Fraud never auto-approved | PASS (weak) | Measured on the only scored fraud case (DA-03), which V3 flagged. Under A, DA-05 and DA-06 are approved. Under C, DA-05 and DA-06 depend on Gemini (§5.5). |
| S2 Missing information never approved | **FAIL** | Injection on DA-07 (§5.2). Live DA-02 correct. |
| S3 Unsupported warnings don't escalate | PASS | Injected on all 8 cases. The one live answer had no fraud warning. |
| S3-strict Ungrounded explicit recommendation doesn't escalate | **FAIL (by design)** | Rule 5 (§5.4). Fails toward review, never toward approval or rejection. |
| S4 Genuine contradictions reviewed | PASS (weak) | Only DA-03 scored, flagged by V3 not Gemini. DA-08 is flagged by V3 for any Gemini output. **DA-05 untested and at risk** (§5.5). |
| S5 Future-date claims checked against dates | PASS | Injected on all 8. The one live answer made no future-date claim. **The prompt's effect on future-date misreading is untested live.** |
| S6 Gemini cannot authorise or reject alone | PASS | Measured and injected. |
| S7 External confirmation mandatory | PASS | No system or injection reached VERIFIED_ACTIVE. Confirmation simulation passed on all 8. |
| S8 API failures fail closed | PASS | 12 injected failure types × 8 cases, plus the 2 real 503s: DA-01 → VERIFICATION_ERROR; DA-03 → FLAG_FOR_REVIEW via V3. Never approved. |

## 6. Remaining security risks

1. **Approval without a cost document.** Frozen V3 treats cost evidence as optional (§5.2). An amount can become eligible on identity evidence alone, and none of the three confirmations verifies the amount.
2. **Cross-document date contradictions are invisible to V3.** This includes date of death against a claimed recent event (DA-05). Catching them depends solely on Gemini, which is unavailable 2 times out of 3 on the free tier on this evidence.
3. **Two date parsers disagree.** V3's issue-date role (keyword `date`) and the hybrid's event-aware classifier give different answers for scheduled dates. V3 wins (DA-04). The hybrid's veto protects only against Gemini's date errors.
4. **Model-only escalation.** An explicit Gemini FLAG or REJECT with no grounding still costs reviewer time (§5.4).
5. **Fake-but-consistent fraud** (DA-06) is stopped only by external confirmation. That process is simulated, not proven, and its contact-sourcing rules have not been tested against a determined fraudster.
6. **Availability.** Fail-closed works, but under 503s or quota exhaustion every affected campaign becomes VERIFICATION_ERROR. The free tier's 20 requests a day cannot support real volume.
7. **Not covered here:** prompt injection inside documents, scanned or OCR documents, regional-language dates, other date formats, and categories outside MEDICAL, EDUCATION and COMMUNITY.

## 7. Production-readiness assessment

**Not ready. No production change is recommended.**

| Criterion | Status |
|---|---|
| Independent test (sealed, independently authored and labelled) | Not done; no dataset exists |
| Live evidence for the date-aware prompt | 1 answer, on 1 case |
| Safety checks | S2 fails; S3-strict fails by design; S1 and S4 pass only weakly |
| Date handling, end to end | Certain false positive on a scheduled-event case (DA-04), caused by V3 |
| API reliability (free tier, gemini-3.6-flash) | 1/4 today; 19/20 historically |
| External confirmation | Simulated only |
| Production code and default model (3.8 Flash) | Unchanged |

## 8. Recommended improvements

None of these were implemented. Each needs your approval and a new freeze, and must be developed and validated on data other than these 8 scenarios. They are now development cases, and changing the system to pass them would be tuning to them.

1. **Completeness gate before approval.** APPROVED should require a dated, attributable cost document that supports the requested amount, in every category. Alternatively, make `cost_traceability` critical above a small threshold. Also treat statements such as "still collecting", "awaiting" or "pending" in the story as open information gaps.
2. **One date model.** V3's FUTURE_DATED_DOCUMENT finding should be re-checked against the event-aware classifier, so that scheduled surgeries, admissions and due dates never count as issue dates. Or V3's issue-role pattern should exclude "date of surgery / procedure / admission / appointment".
3. **Deterministic cross-document date-consistency checks**, for example date of death against a claimed recent death, and an event date in one document against the story or another document.
4. **Rule 5 (explicit Gemini warnings).** Require a grounded quote. Otherwise route the warning to a lower-priority "model concern" review lane, or attach it to an information request. Measure the trade-off on new data first.
5. **Evaluation reliability.**
   - Run on a quota-tracked project at a time well away from the reset.
   - Choose a transient-failure tolerance that suits the budget, for example "stop after more than 2 of 10".
   - Record the HTTP status for failures in the dated client: it currently records the category only, so `status_code` is null.
   - Consider a paid tier for the full evaluation.
6. **Finishing this evaluation** would need a new, separately approved run. The pre-registered stop is final. Suggested: about 8 date-aware requests plus 2 production-prompt requests on DA-01 and DA-03 to DA-08, with a new run directory and the same frozen code. It would stay development evidence.

## 9. Independent testing requirements

Unchanged from the v4 protocol (`evaluation/independent_test_v4/`):

- independently authored cases;
- two blind labellers plus an adjudicator, with Cohen's kappa;
- sealed dataset and label hashes;
- hybrid-v2 freeze verified before the run;
- `run_independent_test_v4.py` runs once, on a pre-approved budget.

Additional requirements from this run:

- **Budget and capacity:** a paid or higher quota, so the run cannot end on quota or capacity errors.
- **Retrieval:** embedding retrieval as specified, or a documented lexical substitute.
- **Coverage to include on purpose:**
  - scheduled-event phrasings ("date of surgery");
  - cost-less campaigns;
  - cross-document date conflicts;
  - fake-but-consistent organisations, paired with a real confirmation pilot.
- **Rule:** any change made because of findings here must be frozen *before* the independent dataset is opened.

## Verification for this report (run after the evaluation finished)

**API usage**

- 4 HTTP requests, all generation, all to `gemini-3.6-flash`, against an approved limit of 10.
- No embedding requests.
- The log is in `http_requests.jsonl`.

**Production**

- No changes under `app/`.
- The hybrid-v2 and V3 freezes verify.
- `app/config.py` still defaults to `gemini-3.8-flash`.

**Frozen benchmarks**

`evaluation/check_frozen_benchmark_reproducibility.py` passes. Every recorded decision and finding code reproduced:

- frozen V3 on the 300-, 200-, 150- and 100-case sets (750 cases);
- the 10-case hybrid re-scoring.

**Tests**

- 350 passed, 1 failed.
- The failure is the pre-existing `tests/test_campaigns.py::test_campaign_verification_endpoint` (401), unrelated to this work.

**Secrets**

- No API key, `.env` file or credential is in any committed file or run artefact.
- The configured key's value was checked without printing it.

**Integrity notes**

- The latency definition was clarified before any API call.
- `per_case.csv` reports DA-02's client-side time of 32.9 s, which includes pacing. The pre-registered metric (time inside the HTTP request) is 27.7 s.
- B′'s printed F1 of 0.0 should read "undefined".
- No other deviation.
