# Authoring guide for the SevaFund independent test set (v4)

You are writing realistic crowdfunding campaigns, with their supporting documents, for an
evaluation. **You will not see the verification system, and you should not try to guess how it
works.** Write cases the way real campaigners, honest or dishonest, would present them.

## What to write

Each case is one JSON object per line in a `.jsonl` file. `example_case.json` shows the fields.

- **Scenario group (`scenario_group`).** A situation you invent: a family, a school, an NGO project.
  Write **1–3 cases per group**, and make them genuinely different (different amounts, documents,
  people, wording). Do not produce near-copies.
- **Category:** `MEDICAL`, `EDUCATION` or `COMMUNITY`.
- **Your intended label (`author_intended_label`):**
  - `legitimate`: genuine need. It may still have incomplete paperwork.
  - `fraudulent`: the campaign misrepresents something material.
  - `borderline`: someone would genuinely need more information to decide.
- **Fraud pattern (`pattern`, fraud cases only).** One of:
  - `consistent_fabrication`: every uploaded document agrees with every other one; the lie only
    shows up when someone contacts the real institution.
  - `independent_record_contradiction`: the uploads agree with each other, but an independent record
    (registry, hospital, school or bank) says otherwise: already paid, registration lapsed, seat
    withdrawn.
  - `suspicious_payee`: the money goes to someone who should not receive it.
  - `keyword_free`: avoid stereotypical scam language entirely. Calm, ordinary wording.
  - `prose_contradiction`: the contradiction sits in narrative sentences, not in form fields.
- **Documents.** Write them as realistic as you can: letterheads, tables, stamps described in text,
  dates in local formats, typos, regional-language headings, OCR-like noise. Vary layouts between
  groups.
- **`gold_evidence_titles`.** The document titles that contain the decisive fact (for fraud and
  borderline cases). For a `consistent_fabrication` case, list the document whose claim the
  institution would deny.
- **`external_environment`.** What each independent party would say if contacted through **its own
  official channel**, for `BENEFICIARY`, `PAYMENT_DESTINATION` and `INSTITUTION`. Each gets an
  `independent_response` of `CONFIRMED`, `CONTRADICTED`, `UNREACHABLE` or `INCONCLUSIVE`, plus a
  short note.
  - If the campaign supplies its own contact for the institution, add `campaign_supplied_contact`
    with `printed_in_uploads` (true/false) and the `response` that contact would give. A fraudster's
    confederate confirms everything.

## Rules

- **No real people's private data.** Invent names, phone numbers and accounts. Real institution
  *names* may be used only with the coordinator's approval; never attach invented misconduct to a
  real institution.
- **Mark provenance.** Set `provenance` to `synthetic`, or to `real_deidentified` only for consented,
  de-identified real material supplied by the coordinator, and set `synthetic` to match.
- **Do not label other people's cases,** and do not discuss your cases with the labellers.
- **Submit only to the coordinator.** The coordinator validates your file
  (`evaluation/validate_independent_submission.py`), records its hash, and stores it outside the
  developers' workspace until the evaluation runs.
