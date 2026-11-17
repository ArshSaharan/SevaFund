# Labelling guide for the SevaFund independent test set (v5)

You label cases written by other people. You never see any system's output, and you work alone. A second labeller labels the same cases independently, and an adjudicator settles disagreements.

**What you read:**
- the cases;
- `REQUIRED_EVIDENCE_POLICY.md`;
- this guide.

You do not read the authors' intended labels, mechanisms, gold titles, declared date facts or notes. The coordinator gives you a blinded copy without them (`prepare_independent_data_v5.py blind`).

**Adjudication.**
- The adjudicator sees both sheets for the disagreeing fields only, and records a value and a reason for each (`adjudication_template.csv`).
- A truth or documentation disagreement that cannot be resolved makes the case `borderline`.
- Agreement (Cohen's κ) is reported for truth, documentation and date checks before adjudication. Every disagreement and decision is kept in the adjudication log.

**One row per case** in `labeling_sheet_template.csv`:

| Column | What to enter |
|---|---|
| `truth_label` | `legitimate`, `fraudulent` or `borderline` (you would genuinely need more information to decide) |
| `documentation` | `complete` or `incomplete`, judged only against the policy |
| `missing_items` | Policy codes that are missing or unacceptable, separated by `;`: `ID`, `NEED`, `COST`, `PAYEE` |
| `detectable_from_dossier` | `yes` if the uploaded material itself shows the problem |
| `detectable_by_external_confirmation` | `yes` if contacting the parties in `external_environment` through official channels would reveal it |
| `decisive_evidence_titles` | Titles of the documents that settle your judgement, separated by `;` |
| `justified_amount_inr` | The amount the documents actually support, after other payers; blank if they support none |
| `acceptable_end_states` | Which outcomes are acceptable, separated by `;`: `APPROVED`, `NEEDS_MORE_INFORMATION`, `FLAG_FOR_REVIEW`. A case with missing items, a fraudulent case or a borderline case never lists `APPROVED` |
| `date_check` | `consistent`, `inconsistent` or `n/a`. Judge whether the case's dates fit each other and its `submitted_on` date (expired documents, scheduled events, impossible sequences). Use `n/a` when no date matters |
| `notes` | Anything the adjudicator should know |

**Labels are final once sealed.** They are hashed before any system runs and never changed after results are seen.
