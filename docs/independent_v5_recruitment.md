# Independent evaluation v5: participant recruitment and effort

**Date:** 2026-11-17.

**Status:**
- No author, labeller, adjudicator or coordinator has been confirmed.
- No design has been selected. Design A remains the preferred full evaluation; design B is the resource-constrained alternative.
- No independent case has been created or labelled.
- The design is chosen only after the feasibility check below passes. The sample size is never reduced without the owner's approval.

## 1. Roles

| Role | Number | What they do | Eligibility |
|---|---|---|---|
| Author | at least 3; 4–6 recommended | Write realistic campaigns (honest and dishonest) with their documents and the external-party responses | Signed independence declaration; "no" to all four involvement questions |
| Labeller | 2 | Label every blinded case independently | As authors; must not have authored cases |
| Adjudicator | 1 | Resolve the labellers' disagreements, with reasons | As authors; not one of the labellers |
| Coordinator | 1 | Recruit, register, distribute packets, run the offline tools, keep identities outside the repository | May be the developer, but then only validates, seals and runs the sealed tools, and reads no case before scoring |

- **One role per person.**
- **Excluded by rule:** the developer (for authoring, labelling and adjudication) and the AI assistant.
- **Useful backgrounds:**
  - *Authors:* people who know how Indian medical, education and community fundraising actually looks, such as hospital billing or front-office staff, social workers, school administrators, NGO programme staff or journalists. Different regions and languages help.
  - *Labellers and adjudicator:* careful document readers, such as people with audit, insurance-claims or caseworker experience.

## 2. Recruitment checklist

**Before approaching anyone**
- [ ] The owner names the coordinator.
- [ ] The owner decides whether participants are volunteers or compensated. Nothing in this plan assumes payment.
- [ ] If the results may be published, check whether the owner's institution requires ethics review for participant involvement.

**For each candidate**
- [ ] Give them a pseudonymous code, for example `A03` or `L01`. Keep real identities outside the repository.
- [ ] Send only the role packet (§4). Never send repository access.
- [ ] Explain the time commitment for the role (§3) and the right to withdraw.
- [ ] Receive the signed `INDEPENDENCE_DECLARATION.md`, with "no" to all four involvement questions.
- [ ] Record the role and the honest `committed_hours` in the participant registry (`independent_test_v5/participants_template.csv` format).

**When enough candidates have committed**
- [ ] `python evaluation/prepare_independent_data_v5.py participants REGISTRY` shows no errors.
- [ ] `python evaluation/prepare_independent_data_v5.py feasibility REGISTRY` shows design A (or B) as feasible. Hours include a 20% buffer for revisions.
- [ ] Plan for about 20% attrition. Recruiting 4–5 authors is the realistic minimum even for design B.
- [ ] The owner selects the design and records it in the pre-registration (`staffing.design_selected`).

**Before any case is written**
- [ ] The owner authorises status APPROVED.
- [ ] `run_independent_test_v5.py preseal-check --registry REGISTRY --out REPORT` passes with no failures and nothing blocking.
- [ ] `run_independent_test_v5.py seal-kit --preseal-report REPORT`.
- [ ] Only then do authors start: first the 6 pilot cases, then the test cases.

## 3. Effort estimate

**Assumptions** (`runner.EFFORT_ASSUMPTIONS`):
- 30 minutes per case, plus 10 minutes per scenario group for the external environment;
- 8 minutes per case per labeller, with 2 labellers;
- 20% of cases have a disagreement, at 10 minutes each to adjudicate;
- 3 minutes of coordination per case.

The "with buffer" figures add 20% for revisions after validator feedback. **These are assumptions, not measurements.** The pilot will show the real authoring time. If it differs materially, the estimate and the feasibility check are re-run before the main authoring starts.

| | Design A (preferred) | Design B (resource-constrained) |
|---|---|---|
| Scenario groups and cases | 270 groups, about 540 cases | 270 groups, 270 cases |
| Authoring | 315 h (378 h) | 180 h (216 h) |
| Labelling | 144 h: 72 h per labeller (86 h each) | 72 h: 36 h per labeller (43 h each) |
| Adjudication | 18 h (22 h) | 9 h (11 h) |
| Coordination | 27 h (32 h) | 14 h (17 h) |
| **Total** | **≈ 504 h (≈ 605 h)** | **≈ 275 h (≈ 330 h)** |

**Per person, with buffer:**

| | Design A | Design B |
|---|---|---|
| Each of 4 authors | ≈ 95 h | ≈ 54 h |
| Each of 6 authors | ≈ 63 h | ≈ 36 h |
| Each labeller | ≈ 86 h | ≈ 43 h |
| Adjudicator | ≈ 22 h | ≈ 11 h |
| Coordinator | ≈ 32 h | ≈ 17 h |

**Calendar, at 4 h a week per person.** Labelling starts only after the full submission is validated and sealed, so the two phases run one after the other.

| | Design A | Design B |
|---|---|---|
| Authoring, 4 authors | ≈ 24 weeks | ≈ 14 weeks |
| Authoring, 6 authors | ≈ 16 weeks | ≈ 9 weeks |
| Labelling (2 labellers) | ≈ 22 weeks | ≈ 11 weeks |
| Adjudication | ≈ 6 weeks | ≈ 3 weeks |
| **Approximate total** | **≈ 44–52 weeks** | **≈ 23–28 weeks** |

At 8 hours a week, the calendar roughly halves. The API run itself (free tier, if the unverified 20-requests-a-day quota holds) adds at least 31 days for A or 16 for B.

**What B gives up** (detail in `docs/independent_v5_readiness.md` §B):
- power to detect small differences from hybrid v2;
- any study of the same situation presented differently;
- half the genuine-but-informal cases.

B keeps all 270 groups, every quota, and the same verdict-level questions.

## 4. How participants contribute without source code or earlier datasets

Participants never get repository access. Everything they see comes from a **role packet** that the coordinator builds outside the repository:

```
python evaluation/prepare_independent_data_v5.py packet author      OUT_DIR
python evaluation/prepare_independent_data_v5.py packet labeller    OUT_DIR --cases BLINDED.jsonl
python evaluation/prepare_independent_data_v5.py packet adjudicator OUT_DIR --cases BLINDED.jsonl --sheet DISAGREEMENTS.csv
```

| Role | Receives | Returns |
|---|---|---|
| Author | `README.md`, `AUTHORING_GUIDE.md`, `REQUIRED_EVIDENCE_POLICY.md`, `example_case.json`, `INDEPENDENCE_DECLARATION.md` | Signed declaration; a `.jsonl` file of cases |
| Labeller | `README.md`, `LABELLING_GUIDE.md`, `REQUIRED_EVIDENCE_POLICY.md`, `labeling_sheet_template.csv`, `INDEPENDENCE_DECLARATION.md`, and the blinded `cases.jsonl` | Signed declaration; a filled label sheet |
| Adjudicator | As the labeller, but with `adjudication_template.csv`, plus the blinded `cases.jsonl` and `disagreements.csv` (only the disputed fields, with both values) | Signed declaration; a filled adjudication sheet |

**What the tool enforces:**
- **Allowlist.** Files come from an allowlist only, and the packet is rejected if anything else appears in it.
- **No code.** A packet never contains code, prompts, rule or keyword lists, earlier datasets or system outputs.
- **Outside the repository.** The packet is built outside the repository; building it inside is refused.
- **Blinding.** The blinded cases are checked: any field hidden from labellers (author intent, mechanism, gold titles, date facts, detectability intent) makes the build fail.
- **Pilot cases are never labelled.** Only `T5-` (or engineering `ENG-`) cases are accepted.
- **Role limits.** Authors cannot receive cases or sheets, and only the adjudicator receives the disagreement sheet.
- **Record.** `packet_manifest.json` records the SHA-256 of every file, so the coordinator can show exactly what each person received.

**How work flows:**
1. Participants work offline in any text editor or spreadsheet program, and send files to the coordinator only, never to developers.
2. The coordinator runs the validator. Authors receive only the validator's error list by case ID and fix their own cases; the coordinator never edits a case.
3. Blinded copies go to the labellers.
4. Only the disputed fields go to the adjudicator.
5. Authors never see labels, and labellers never see author intent or any system output.

**Limits to be aware of:**
- The authoring guide necessarily describes fraud *mechanisms*, so authors can write varied fraud. It does not describe how the system detects anything.
- Hand-writing JSON may be hard for non-technical authors. The 6 pilot cases test this first. A simpler entry format (for example, a spreadsheet converted by a tool) would be new tooling and needs approval.
- If the coordinator is the developer, the coordinator's exposure is the main residual independence risk. The rule is that the coordinator does not read cases before scoring.
