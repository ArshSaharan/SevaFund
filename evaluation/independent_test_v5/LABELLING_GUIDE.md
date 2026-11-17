# Labelling guide for the SevaFund independent test set (v5)

You label cases written by other people. You never see any system's output, and you work alone. A second labeller labels the same cases independently, and an adjudicator settles disagreements.

**What you read:**
- the cases;
- `REQUIRED_EVIDENCE_POLICY.md`;
- this guide.

You do not read the authors' intended labels or their notes; the coordinator removes those fields before giving you the cases.

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
| `notes` | Anything the adjudicator should know |

**Labels are final once sealed.** They are hashed before any system runs and never changed after results are seen.
