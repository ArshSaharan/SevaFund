# Protocol for a genuinely independent SevaFund test set (v4)

This protocol replaces `final_test_protocol_v2.md` and `final_test_protocol_v3.md` for any future
**performance claim**. Every dataset used so far (the 200-, 100-, 150- and 300-case sets and the V1,
V2 and V3 development sets) was written by a developer of the verifier, built from templates, and
inspected during development. None of them can support an independent claim.

## 1. What went wrong before, and the rule that prevents it

| Observed problem | Rule in this protocol |
|---|---|
| The system's developer wrote the cases and labels, sometimes the same agent and sometimes in the same session. | Cases are written and labelled by people who have never seen the verifier code, its rule vocabulary, or any earlier corpus. |
| 10 cases per template family, all receiving the same decision (ICC = 1.0). 300 cases gave about 30 independent observations. | At most 3 cases per scenario group, each meaningfully different. The unit of analysis is pre-registered as the group. |
| Fabricated-but-consistent fraud was "true" only in the author's head, so no system could be tested against it. | Every case comes with a **simulated external-contact environment** (section 3), so external confirmation can be evaluated end to end. |
| The held-out split contained only one kind of fraud. | Each fraud pattern appears in every split and every category (section 2). |
| A test generator was written during development. | The test set is produced after the freeze, by the independent authors, and stored outside the developers' workspace until it is run. |

## 2. Content requirements

**Minimum groups per category.** Medical, education and community each need at least:
- 30 legitimate groups,
- 30 fraudulent groups,
- 15 borderline groups,

with 1–3 cases per group. That gives at least 225 groups and roughly 450 cases.

**Why that size.** At about 90 fraud groups, a recall near 60% has a Wilson 95% interval of about
±10 points at the group level. With 30 groups it is about ±17 points.

**Fraud patterns.** Each must be at least 15% of fraud groups, in every category:

1. **Internally consistent fabricated documents.** Nothing in the dossier contradicts anything else.
   Only the external-contact environment reveals the fraud: for example, the hospital's independent
   line has no record of the patient.
2. **Contradictions with independent records.** The uploaded documents agree with each other, but a
   registry or institution record contradicts them: the registration has lapsed, the fee was already
   paid, the seat was withdrawn.
3. **Suspicious payment destinations.** A payout account belongs to an unrelated individual, an
   "agent", or a newly opened account whose holder name differs from the institution's.
4. **Fraud without obvious red-flag keywords.** The case must contain none of the words in
   `app/services/fraud_detector.py` (RED_FLAG_PATTERNS) or the V2/V3 semantic lexicons; a script
   checks this, and the authors must not see the word list.
5. **Cross-document contradictions in free prose** rather than in form fields.

**Legitimate cases must include:**
- incomplete documentation, for example a missing optional document or a provisional estimate later
  confirmed;
- high but justified costs;
- regional-language headings, scans and OCR noise;
- campaigns written by someone other than the beneficiary (a parent, a teacher, an NGO volunteer).

**Borderline cases** genuinely need more information to decide. Their adjudicated expected outcome
is NEEDS_MORE_INFORMATION or FLAG_FOR_REVIEW, never APPROVED.

**Real data.** Where obtainable, include de-identified real dossiers. That requires consent, a
data-processing agreement, and redaction of names, phone numbers, account numbers and identifiers
before any external model sees them; the framework's `--data-authorization` guard enforces this.
Report real and synthetic results separately.

## 3. Simulated external-contact environment

Every case comes with a sealed `external_environment` record describing what each independent party
would say if contacted:

- **beneficiary:** whether the platform's KYC matches;
- **payment destination:** the bank account-holder name and its link to the institution;
- **institution:** what the hospital, institution or registry would confirm, using contact details
  from an independent directory;
- **campaign-supplied contacts:** what the contacts printed in the uploads would claim. These can be
  confederates who "confirm" anything.

An evaluator plays the verifier role by recording `ConfirmationRecord`s. It may consult only the
independent contacts, plus the campaign-supplied ones to test that they are never accepted. This
makes it possible to measure what the approval workflow is for: **how many fraudulent campaigns
reach VERIFIED_ACTIVE**, and how many contacts that costs.

## 4. Labelling

- Two labellers per case, working independently and blind to every engine's output. Each assigns:
  - the label (`legitimate | fraudulent | borderline`);
  - the expected workflow end state;
  - whether the fraud is *detectable from the dossier* or only *through external confirmation*;
  - `gold_evidence_titles`: the documents that establish the decisive fact, used for
    retrieval recall@k and MRR.
- Disagreements are adjudicated by a third person. Report Cohen's κ before adjudication.
- Labels are hashed and frozen before any engine runs. A label is never changed after results are
  seen.

## 5. Pre-registered analysis

- **Unit:** the scenario group. The primary results are:
  - group-level recall and false-positive rate, with Wilson intervals over groups;
  - case-level rates with cluster-bootstrap intervals (`evaluation/group_uncertainty.py`);
  - ICC and effective sample size.
- **Fraud detection:** FLAG_FOR_REVIEW or REJECTED only. ELIGIBLE_PENDING_CONFIRMATION and
  NEEDS_MORE_INFORMATION are not detections. Borderline cases count as negatives, with a secondary
  analysis that excludes them.
- **Approval safety, reported separately:**
  - automatic activations (must be 0);
  - fraud reaching ELIGIBLE_PENDING_CONFIRMATION;
  - fraud reaching VERIFIED_ACTIVE after the simulated confirmation step;
  - fraud accepted on campaign-supplied contacts (must be 0).
- **Workload, reported separately:** manual reviews, information requests and external contacts
  per 100 campaigns; and legitimate campaigns delayed by avoidable requests.
- **Systems:**
  - frozen V3 plus the approval workflow;
  - V2 and V1 as comparators;
  - optionally, the Gemini configurations through `evaluation/gemini_evaluation_framework.py`, with
    API failures and coverage reported separately and metrics computed on the paired-complete
    subset.
- **Paired comparisons:** McNemar's test at group level for each pair of systems.

## 6. Execution

1. Freeze every system under test, with hashes recorded in a manifest, before the test set exists.
2. Run each system once. The runner refuses to reuse its output directory.
3. Do not inspect individual cases until every metric has been written.
4. Defects found during the test are reported, not fixed. Fixes go into a new version, which needs
   a new test set.

## 7. Reporting

Publish all of the following:

- group-level and case-level tables;
- every misclassified group, with findings and redacted audit records;
- the workflow end states;
- the contact workload;
- κ;
- the provenance of every case (independent author, real or synthetic).

State plainly that internally consistent documents are not proof of authenticity. The tested
system's safety rests on the external-confirmation step, so the results are only as good as the
contact environment's realism.
