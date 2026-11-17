# Authoring guide for the SevaFund independent test set (v5)

You are writing realistic crowdfunding campaigns, with their supporting documents, for an evaluation.

**What you must not see.** You will not see the verification system, the platform's internal rules or any earlier test data, and you should not try to guess how the system works. Write cases the way real campaigners, honest or dishonest, would present them.

**What you may read:**
- this guide;
- `REQUIRED_EVIDENCE_POLICY.md`, the platform's public documentation policy;
- `example_case.json`.

## What to write

Write one JSON object per line in a `.jsonl` file. The example shows every field.

- **Scenario group (`scenario_group`).** A situation you invent: a family, a school, an NGO project.
  - Write **1–3 cases per group**, and make them genuinely different: different amounts, documents, people and wording.
  - Never write near-copies.
- **Category:** `MEDICAL`, `EDUCATION` or `COMMUNITY`.
- **Your intended label (`author_intended_label`):**
  - `legitimate`: genuine need.
  - `fraudulent`: the campaign misrepresents something material.
  - `borderline`: a careful reviewer would genuinely need more information to decide.
- **Documentation (`author_intended_documentation`):**
  - `complete`: every item in the policy is present.
  - `incomplete`: something required is missing or unacceptable.

  For genuine incomplete cases, set `incomplete_subtype` to one of:
  - `no_cost_document`;
  - `unacceptable_cost_document`: expired, issuer not identifiable, or below the amount requested;
  - `missing_identity_or_need`;
  - `genuine_but_informal`: the family genuinely cannot get a formal quotation, for example from a government hospital or informal tutoring.
- **How the fraud works (`mechanism`, fraud cases only):**
  - `consistent_fabrication`: every document agrees with every other one; the lie only shows when someone contacts the real institution.
  - `independent_record_contradiction`: the uploads agree, but an independent record says otherwise (already paid, seat withdrawn, registration lapsed).
  - `suspicious_payee`: the money goes to someone who should not receive it.
  - `document_contradiction`: identity, dates, treatment or amounts conflict between documents, or between the story and the documents. Set `form` to:
    - `structured`: the conflict is in dates, IDs or amounts;
    - `prose`: the conflict is in narrative sentences.
  - `amount_inflation`: the need is genuine but the goal overstates it. For example, the quote is altered, insurance already pays, or the same bill appears twice.
  - `misrepresented_need`: the documents show the treatment or purpose is not needed or not happening.
- **`keyword_free`.** Set this to `true` for a fraud case written in calm, ordinary language with no stereotypical scam wording. Aim for about a third of your fraud cases.
- **`submitted_on`.** The date the campaign is submitted, as `YYYY-MM-DD`. Write every document date as a real calendar date that makes sense relative to it. Future dates are fine for scheduled events, such as a surgery date.
- **Documents.** Make them realistic:
  - letterheads, tables, and stamps described in text;
  - local date formats;
  - typos, regional-language headings and OCR-like noise.

  Vary layouts between groups. Give some cases more than five documents or long documents.
- **`gold_evidence_titles`.** The titles of the documents that contain the decisive fact. These are required for fraud, borderline and incomplete cases.
- **`external_environment`.** What each party would say if the platform contacted it through **that party's own official channel**:
  - `BENEFICIARY`, `PAYMENT_DESTINATION` and `INSTITUTION`: each gets an `independent_response` of `CONFIRMED`, `CONTRADICTED`, `UNREACHABLE` or `INCONCLUSIVE`, plus a short note.
  - `COST_ISSUER`, the party that issued the cost document: its `independent_response`, plus:
    - `amount_stated_inr`: what its billing or accounts office would state, or `null` if it would not disclose;
    - `other_payers_inr`: amounts already covered by insurance, a scheme, a scholarship or an advance;
    - a note.
  - If the campaign prints its own contact for a party, add `campaign_supplied_contact` with `printed_in_uploads` (true or false) and the `response` that contact would give. A fraudster's confederate confirms everything.
- **`llm_assisted`.** Set this to `true` if any language model helped draft the case. Be honest. These cases are still useful but are reported separately.

## Rules

- **No real people's private data.** Invent names, phone numbers and account numbers.
- **Real institution names** may be used only with the coordinator's approval. Never attach invented misconduct to a real institution.
- **Provenance.** Set `provenance` to `synthetic`, or to `real_deidentified` only for consented, de-identified material the coordinator supplies.
- **Keep your cases to yourself.** Do not label anyone's cases, and do not discuss your cases with labellers or developers.
- **Submit only to the coordinator,** who validates the file, records its hash and stores it outside the developers' workspace.
- **Pilot cases.** The coordinator will also ask for 6 pilot cases. They are used only to test the pipeline and are never scored.
