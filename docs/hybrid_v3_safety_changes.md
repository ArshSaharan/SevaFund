# Hybrid v3: safety fixes after the date-aware evaluation (development only)

**Status:** implemented and tested offline on `dev/verifier-v2-v3-evaluation`. Policy `hybrid-v3-dev-1`.

- No Gemini API call was made.
- Production is unchanged.
- Frozen V3, frozen hybrid v2 and every previously recorded result are unchanged and still reproduce.

**Classification:** every number below is **development evidence**:

- the DA cases motivated these changes;
- the benchmark sets were used to develop V2 and V3;
- the new regression tests were written by the developer.

None of it is an independent evaluation, and none of it supports a claim of better real-world accuracy.

## 1. Design: a new layer, nothing frozen edited

Fixing V3 in place would break the V3 and hybrid-v2 freeze manifests and change the recorded benchmark results. Instead, a new development package, `app/services/development_hybrid_v3/`, wraps the frozen code:

| Module | Purpose |
|---|---|
| `dates.py` | Event-aware date model: issue, validity, relative validity, scheduled event, completed event, mention |
| `financial.py` | Financial-evidence gate |
| `crossdoc.py` | Deterministic cross-document checks, plus the explicit `GEMINI_DEPENDENT` list |
| `confirmation.py` | Explicit activation guard on the frozen approval workflow |
| `policy.py` | Combines frozen V3, the new layers and frozen hybrid v2's Gemini concern triage; re-checks two kinds of V3 finding |

The Gemini prompt and client are unchanged (frozen hybrid v2).

**Policy order (first match wins):**

1. V3 error → VERIFICATION_ERROR.
2. V3 contradiction (after the re-checks) → V3's decision.
3. Deterministic cross-document contradiction → review.
4. Future-dated document or record → review.
5. Gemini failed → VERIFICATION_ERROR.
6. Gemini explicit FLAG or REJECT → review, never rejection.
7. Grounded Gemini contradiction → review.
8. Any open evidence → NEEDS_MORE_INFORMATION, listing every request.
9. Everything passes → APPROVED, which means ELIGIBLE_PENDING_CONFIRMATION with authenticity UNCONFIRMED.

## 2. Change summary, by issue

### 2.1 Missing cost documentation (DA-07)

**Rule:** approval now requires a valid financial document that establishes the amount. A financial document must meet all of the following:

- **Type:** it is a cost instrument — estimate, quotation, invoice, bill, fee demand, notice, structure or statement, challan, cost schedule, budget, proforma, ledger, demand or debit note, or work, equipment or purchase order. Either its type or title says so, or one of its first lines begins with the instrument ("Quotation No. …").
- **Not excluded:** certificates, bonafide or enrolment letters, resolutions, minutes, reports, summaries and prescriptions are never financial documents. A letter that mentions a figure in a sentence never establishes the amount.
- **Amount:** it carries a payable amount, taken in this order:
  1. the outstanding balance, when the document also records a payment, advance or cover;
  2. otherwise the total;
  3. otherwise the sum of its itemised lines.
- **Traceable:** at least two of issuer, date, reference number and signatory.
- **Current:** not expired. This covers "valid until …", relative validity ("valid for 60 days", "one year from the date of issue") and time-sensitive documents older than 365 days. It is also not future-dated.
- **Sufficient:** the goal is at most 5% above the documented need. The need is the largest single document, or the sum across different issuers.

**Outcomes:** anything short of this produces NEEDS_MORE_INFORMATION with a specific request — never approval. The statuses are MISSING, EXPIRED, UNTRACEABLE, NO_AMOUNT and INSUFFICIENT_AMOUNT.

### 2.2 Contradictory documents (DA-05)

New deterministic checks. Each one sends the case to review with the basis DETERMINISTIC_FINDING.

| Check | Fires when |
|---|---|
| DEATH_DATE_CONFLICT | Two dates of death are more than 2 days apart (documents and story) |
| EVENT_DATE_CONFLICT | The story dates a completed admission, discharge or procedure (or a scheduled procedure), and no document date for the same event is within 2 days |
| PATIENT_ID_CONFLICT | The same identifier type (UHID, MRN, IP/OP number, patient ID, roll, enrolment or admission number) differs across documents that name the beneficiary |
| AGE_CONFLICT / SEX_CONFLICT | The beneficiary's age differs by more than 1 year, or their sex differs |
| TREATMENT_NOT_INDICATED | The campaign asks for a procedure family that a document says is not indicated or not advised, or that the document says should be managed conservatively |
| OUTSTANDING_AMOUNT_CONFLICT | Documents from the same issuer state outstanding amounts differing by more than 2% and more than ₹1,000 |

The scope is deliberately narrow, to limit false positives: several admissions or procedures can be genuine, so only death dates are compared document against document.

**Still dependent on Gemini or on external confirmation.** This list is coded as `GEMINI_DEPENDENT`, and a test demonstrates the first item:

- place or circumstance contradictions with no date difference (for example, "died at home" against "died in the ICU");
- treatment mismatches expressed through synonyms;
- a diagnosis inconsistent with the treatment;
- several conflicting admissions or procedures;
- relationship claims not written as a name, age, sex or identifier;
- cost plausibility beyond V3's typical-range table;
- unusual or regional date formats, or scans without text;
- narrative contradictions with no labelled field;
- fabricated but consistent documents, which nothing in the text can reveal.

### 2.3 Fabricated institutions (DA-06)

- **Approval wording:** the approval reason now states that consistency is not proof of authenticity. Every result carries `authenticity: UNCONFIRMED`.
- **Institution check:** the policy starts the frozen workflow with `names_institution=True`, so the institution check is always required.
- **Activation guard:** `confirmation.activation_status` allows activation only when the frozen workflow is VERIFIED_ACTIVE **and** all three checks (beneficiary, payment destination, institution) were each confirmed through an independent source.
- **Tested scenarios:**
  - no confirmation;
  - only campaign-supplied contacts;
  - institution unconfirmed;
  - institution unreachable;
  - institution contradicts, which goes to review;
  - a reviewer trying to activate directly, which is refused;
  - positive control: all three confirmed independently, which activates.

### 2.4 Date interpretation (DA-04)

**The new date model:**

- A date introduced by "date of <event>" or "<event> date" (surgery, admission, appointment and so on) is an **event** date, never the issue date.
- Planning words ("proposed", "scheduled", "will be", "next", "due") make it **scheduled**. Scheduled dates are never judged future-dated.
- A completed event is judged future-dated when it is described in the past tense ("discharged on", "who expired on"), or labelled "date of discharge / death / …" in a retrospective record such as a discharge summary, bill, receipt, report or certificate.
- Issue dates are recognised from "Date:", "dated", "bill / report / … date", "issued on", or an unlabelled date in the header.
- Expiry dates are recognised from "valid until / expires" and from relative validity.
- Staleness (older than 365 days) applies only to time-sensitive documents. A three-year-old society registration is valid; a 500-day-old income certificate is expired.

**Frozen V3 re-checks, rather than edits.** V3's own findings are re-checked, and V3's frozen decision rule is re-run on the findings that remain:

- **FUTURE_DATED_DOCUMENT:** dropped when every occurrence of the date is scheduled or merely mentioned. This fixes DA-04.
- **AMOUNT_UNSUPPORTED / AMOUNT_EXCEEDS_BALANCE:** dropped when the "documented amount" is a four-digit year that only appears inside a date. This V3 bug was **found by the new tests**: V3 read "/2026" in "valid until 27/12/2026" as a documented total of ₹2,026 and flagged a ₹3,20,000 request as 157.9 times that.

### 2.5 Gemini warning handling

- **Explicit warnings:** an explicit Gemini FLAG or REJECT still goes to manual review. Rejection never comes from Gemini.
- **Review basis:** every review now records why it was raised:
  - `DETERMINISTIC_FINDING` — V3, a cross-document check or a future-dated record;
  - `DOCUMENT_SUPPORTED_MODEL_FINDING` — Gemini's quote is found in the retrieved documents;
  - `UNVERIFIED_MODEL_SUSPICION` — an explicit Gemini warning with no supporting quote, shown to the reviewer as a suspicion to check, not a finding.
- **Ungrounded warnings:** a warning with no supporting quote, attached to an approval or an information request, becomes a "Clarify (unverified model concern)" item. It never escalates and never approves.

## 3. Before and after on the affected cases

The DA cases are development cases. Gemini answered live for DA-02 only, so every case is shown under scripted Gemini outputs. Source: `evaluation/runs/hybrid_v3_offline_20261117T091013Z`.

| Case | Label | Gemini output | Hybrid v2 (before) | Hybrid v3 (after) |
|---|---|---|---|---|
| **DA-07** incomplete | legit | approves | **APPROVED** | **NEEDS_MORE_INFORMATION** (financial evidence missing) |
| DA-07 | legit | information request + ungrounded warning | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| DA-07 | legit | failed | VERIFICATION_ERROR | VERIFICATION_ERROR |
| **DA-05** death dates | fraud | approves | **APPROVED** | **FLAG_FOR_REVIEW** (DEATH_DATE_CONFLICT) |
| DA-05 | fraud | failed | VERIFICATION_ERROR | **FLAG_FOR_REVIEW** (deterministic; no Gemini needed) |
| DA-05 | fraud | information request + ungrounded warning | NEEDS_MORE_INFORMATION | **FLAG_FOR_REVIEW** |
| **DA-04** scheduled surgery | legit | approves | **FLAG_FOR_REVIEW** (V3 future-date) | **NEEDS_MORE_INFORMATION**: V3 finding refuted; see §5 for the residual V3 issue |
| DA-04 | legit | failed | FLAG_FOR_REVIEW | VERIFICATION_ERROR |
| DA-04 | legit | ungrounded FLAG | FLAG_FOR_REVIEW (V3) | FLAG_FOR_REVIEW, basis UNVERIFIED_MODEL_SUSPICION |
| **DA-06** fabricated trust | fraud | approves | APPROVED → pending confirmation | APPROVED → pending confirmation, authenticity UNCONFIRMED, 3 independent confirmations required |
| DA-02 expired notice | legit | **live answer** | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION (unchanged) |
| DA-03 future-dated | fraud | any | FLAG_FOR_REVIEW (V3) | FLAG_FOR_REVIEW (V3), plus EVENT_DATE_CONFLICT recorded |
| DA-08 genuine-looking | fraud | any | FLAG_FOR_REVIEW (V3) | FLAG_FOR_REVIEW (V3), plus TREATMENT_NOT_INDICATED recorded |
| DA-01 valid | legit | approves | APPROVED | APPROVED (unchanged) |
| any of DA-01, 02, 04, 05, 06, 07 | — | ungrounded FLAG | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW, now labelled UNVERIFIED_MODEL_SUSPICION (except DA-05, which is DETERMINISTIC_FINDING) |

**The 10 historical cases** (saved production-prompt outputs, in-sample): the hybrid v3 decision equals the hybrid v2 decision on all 10. Trigger labels differ in only two ways:
- two renames: `GEMINI_EXPLICIT_FRAUD_WARNING` → `GEMINI_EXPLICIT_WARNING` (V3T-244, now with basis DOCUMENT_SUPPORTED_MODEL_FINDING) and `BOTH_APPROVE` → `ALL_CHECKS_PASS` (V3T-224);
- on V3T-194, V3T-024 and E150-102, the financial gate is now the first-listed reason. All three were already NEEDS_MORE_INFORMATION.

## 4. Expected effect on false positives, recall, reviews and information requests

**Benchmark sets, deterministic layers only.** Gemini is assumed to approve every case cleanly (the most permissive output), so every difference comes from the new code. Under that assumption, hybrid v2 equals V3 alone on these sets.

| Set (labels) | System | Fraud detected | Fraud approved | Legit escalated | Legit approved | Info requests | Manual reviews |
|---|---|---|---|---|---|---|---|
| 300 (100 fraud / 100 legit / 100 borderline) | hybrid v2 | 60/100 | 20 | 0/100 | 100/100 | 100 | 60 |
| | **hybrid v3** | 60/100 | 20 | 0/100 | **90**/100 | **120** | 60 |
| 200 (80 / 80 / 40) | hybrid v2 | 20/80 | 0 | 0/80 | 80/80 | 100 | 20 |
| | **hybrid v3** | 20/80 | 0 | 0/80 | **72**/80 | **108** | 20 |
| 150 (60 / 60 / 30) | hybrid v2 | 10/60 | 36 | 0/60 | 45/60 | 59 | 10 |
| | **hybrid v3** | 10/60 | **0** | 0/60 | **0**/60 | **140** | 10 |
| 100 (40 / 40 / 20) | hybrid v2 | 6/40 | 8 | 0/40 | 6/40 | 77 | 8 |
| | **hybrid v3** | 6/40 | **0** | 0/40 | **0**/40 | **92** | 8 |

On these 750 cases the cross-document checks and both V3 re-checks changed nothing: no new detections and no new false positives. **Every change came from the financial gate.**

**Totals**

- Fraud approvals: 64 → 20 (−44). They became information requests, not detections.
- Legitimate approvals: 231 → 162 (−69).
- Information requests: 336 → 460 (+124).
- Legitimate escalations: unchanged at 0.
- Manual reviews: unchanged at 98.

**Why the 150- and 100-case sets go to zero approvals.** Their "legitimate" cases mostly attach summary records ("the fare schedule and clinic estimate together fit the requested amount") or bare synthetic notes with no issuer, date or reference. No cost document exists, so the gate asks for one, as specified. The 20 fraud approvals left in the 300-case set are fake-but-consistent dossiers with proper cost documents; only external confirmation can stop them.

**Expected direction on real campaigns.** This is reasoned from the mechanisms; it has not been measured.

| Metric | Expected change | Why |
|---|---|---|
| False positives | **Down** | Date-misread V3 flags are removed (DA-04 type, and years read as amounts) |
| False positives | **Up, slightly** | Any cross-document rule can misfire: typing errors in identifiers or ages, two patients in one dossier, "not indicated" written about a sub-procedure. None fired wrongly on the 760 benchmark and historical cases, but real documents are messier. |
| Fraud recall | **Up** for date, identity, treatment and amount contradictions | DA-05 is now flagged without Gemini |
| Fraud recall | **Unchanged** for fabricated but consistent dossiers | Nothing in the text reveals them |
| Fraud recall | **Unchanged** wherever the cost gate fires | The gate produces information requests, not detections |
| Manual reviews | **Up** | Cross-document flags |
| Manual reviews | **Down** | Refuted V3 date flags |
| Manual reviews | **Unchanged** | Explicit Gemini warnings still reach review, now labelled by basis |
| Information requests | **Up substantially** | The main cost of the change. Legitimate applicants without a formal quotation or fee demand are asked for one. |
| Unsafe approvals | **Down** | Approval now requires documented cost and no open items |

## 5. Tests

**New tests:** `tests/test_hybrid_v3.py`, 71 tests, all passing. They use new scenario texts written for the tests, not the DA texts.

- **Financial gate:**
  - a school letter alone never establishes the amount;
  - a traceable, current quotation does;
  - 5% tolerance (borderline);
  - expired, untraceable and insufficient-amount documents;
  - an order with a total counts; a sentence mentioning an estimate does not.
- **Cross-document checks:**
  - death-date conflict, under all 6 scripted Gemini outputs;
  - death dates 1 day apart (borderline, no flag);
  - story discharge date against the record, inside and outside tolerance;
  - patient-identifier conflict;
  - an identifier belonging to another person is not compared;
  - age and sex;
  - "not advised" for the claimed treatment against a different treatment;
  - same-issuer outstanding amounts;
  - an explicit test showing that a place-of-death contradiction is *not* caught deterministically.
- **Confirmation:** no, partial, campaign-supplied and contradicted confirmations; a reviewer trying to activate; the positive control.
- **Dates:**
  - "Date of surgery", "Surgery date", "Proposed date of surgery", "Admission on" and "Next review on" are never future-dated;
  - a future "Bill date" and a future "Date of discharge" in a discharge summary are;
  - explicit and relative expiry;
  - time-sensitive staleness;
  - V3 re-checks: a future-date finding on a scheduled surgery, and a year read as an amount;
  - a future-dated bill is still flagged.
- **Gemini lanes:** grounded, ungrounded, rejection never final, ungrounded warning with approval, API failure.
- **Exhaustive no-approval check:**
  - 15 base cases (the new fixtures plus all 8 DA cases), every subset of their documents, and 6 Gemini outputs;
  - APPROVED occurs only with a clean Gemini approval, supported financial evidence, V3 effectively approving, no open items, no cross-document finding and no unverified concern;
  - an approval always goes to ELIGIBLE_PENDING_CONFIRMATION with authenticity UNCONFIRMED and three required confirmations;
  - nothing ever reaches VERIFIED_ACTIVE.
- **Labelled scenarios:** legitimate, incomplete, borderline and fraudulent.
- **DA regressions.**
- **Integrity:** both freezes verify, and production code does not import the new package.

**Full suite:** 421 passed, 1 failed. The failure is the pre-existing `tests/test_campaigns.py::test_campaign_verification_endpoint` (HTTP 401), unrelated to this work.

During development, the date-aware runner's pre-flight test failed while the new package was uncommitted. That is its guard against uncommitted changes under `app/` working as designed, and it passed once the package was committed.

**Frozen benchmarks:** `evaluation/check_frozen_benchmark_reproducibility.py` passes:

- all 750 frozen-V3 decisions and finding codes (300 / 200 / 150 / 100 cases);
- the 10-case hybrid re-scoring;
- both freeze manifests;
- unchanged benchmark datasets.

### Disclosed development adjustments (made before this report, all in-sample)

1. **Financial-document classifier:**
   - after inspecting gate outcomes on the benchmark sets, I added order instruments and the "first line starts with an instrument" rule;
   - I also improved issuer, reference and signatory detection: "[Page 1] Deccan Institute …", "Record TUITION-001".
2. **Balance rule:** a new test showed that a line item called "balance" was being read as the outstanding need. A balance now counts only after a payment, advance or cover.
3. **Year-as-amount V3 bug:** found by a new test, and handled by the re-check in §2.4.
4. **Three test fixtures adjusted:**
   - "tuition fee balance" reworded to "for the year", because it legitimately triggers V3's balance check;
   - a too-short quotation lengthened, because V3 treats fewer than five words as unreadable;
   - the patient-ID assertion relaxed to "flagged, and the new finding recorded", because frozen V3's IDENTIFIER_CONFLICT already catches that case first.

## 6. Remaining risks that code cannot resolve

1. **Fabricated but internally consistent dossiers** (DA-06, and the 20 fraud approvals in the 300-case set). Only external confirmation can stop them. Its strength depends on:
   - operations: independently sourced contacts, resistance to social engineering, and no collusion by institution staff;
   - none of which is measured. The confirmation pilot has not been run.
2. **Issuer authenticity and insider fraud.** A genuine institution's staff can issue genuine-looking but false documents. Text checks cannot detect this.
3. **Amount verification in confirmations.** For community and organisation campaigns, the frozen workflow's institution check confirms registration, not the supplier's quotation. A cost-issuer confirmation step needs a workflow change, which modifies a frozen package and requires your approval.
4. **Gemini-dependent contradictions** (§2.2 list). These rely on Gemini, which was available for only 1 of 3 non-quota requests on the free tier in the last run, or on a reviewer.
5. **Burden on genuine applicants.** Requiring formal cost documents will delay campaigns from people who cannot easily get a quotation. Whether that trade-off is acceptable is a policy decision, not a code question.
6. **Real-document variability.** Scans, OCR errors, regional languages and unusual date formats fall outside what the deterministic parsers were tested on.
7. **Judgement thresholds:**
   - 5% amount tolerance;
   - 2-day date tolerance;
   - 1-year age tolerance;
   - 365-day staleness;
   - traceability of 2 out of 4.

   These are reasoned defaults, not calibrated values.
8. **Residual V3 limitation on DA-04.** After the date fix, V3 still raises an uncertain `SERVICE_UNRELATED` finding because its lexicon does not link "palatoplasty" to "cleft palate repair". The case therefore gets an information request instead of becoming eligible. This was not changed.
9. **No independent evidence.** All the numbers here are development numbers. Only the sealed v4 independent test can say how the system performs on unseen, independently labelled cases.

## 7. Integrity and production

**Unchanged:**

- Frozen V3: package, configuration and freeze manifest.
- Frozen hybrid v2: package, framework, workflow and freeze manifest.
- The date-aware live run directory and every earlier run directory, verified with `git diff`.
- Production: `app/services/ai_verifier.py`, `rag.py`, `gemini_api.py`, `fraud_detector.py`, `app/config.py` (default `gemini-3.8-flash`) and `app/schemas/ai.py`. Their hashes are checked by the hybrid-v2 freeze.

**New, development only:** `app/services/development_hybrid_v3/` (not imported by any production module; a test checks this), `evaluation/compare_hybrid_v3_offline.py`, `tests/test_hybrid_v3.py`, `evaluation/runs/hybrid_v3_offline_20261117T091013Z/` and this report.

**Process:**

- No API calls.
- No push, merge or deploy.
- Secret scan clean: the configured key's value was checked without being printed.

**Before any further evaluation, with your approval:**

1. Freeze hybrid v3 with a hash manifest.
2. Use new scenarios, not the DA cases, or run the sealed independent test.
3. Agree an API budget suited to the free tier's reliability.
