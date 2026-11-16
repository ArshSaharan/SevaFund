# Controlled Gemini 3.6 Flash evaluation — 10 scenario groups (gemini_eval_v1_3_6)

> **Diagnostic testing on previously available synthetic data; not independent validation.** Synthetic, single-author data; 10 cases. These results do not establish real-world accuracy or production readiness.

## 1. Executive summary

* Gemini generation: 19/20 succeeded (Wilson 95% 76%–99%); 0 timeouts, 1 server errors; mean latency 45.5 s, p95 72.5 s.
* API requests used: {'generation': 20, 'embedding': 10} of the approved budget {'generation': 20, 'embedding': 10}; stop reason: None.
* Fraud detection (FLAG/REJECT only), recall on 4 fraud cases: Heuristics, no documents 4/4; Deterministic fallback (heuristics + lexical retrieval) 2/4; Gemini 3.6 Flash, no documents 0/4; Gemini 3.6 Flash + RAG 3/4; Frozen V3 2/4; Frozen V3 + Gemini (combined) 4/4.
* Legitimate campaigns escalated to review/rejection: Heuristics, no documents 4/4; Deterministic fallback (heuristics + lexical retrieval) 2/4; Gemini 3.6 Flash, no documents 0/4; Gemini 3.6 Flash + RAG 0/4; Frozen V3 0/4; Frozen V3 + Gemini (combined) 2/4.
* See section 11 for the interpretation and recommendation.

## 2. Dataset and scenario-group selection

| Case | Group | Category | Label | Keyword-free | Selection reason |
|---|---|---|---|---|---|
| V3T-064 | internally_consistent_but_forged_clinic_file | MEDICAL | fraudulent | yes | Fraud with internally consistent but fabricated paperwork (estimate and service note agree); no red-flag keywords; frozen V3 approves this group. |
| V3T-244 | supplier_ledger_closed | COMMUNITY | fraudulent | no | Fraud contradicted by an independent record (supplier ledger shows the invoice already paid and the account closed); frozen V3 misses this group. |
| V3T-154 | equipment_dispatch_shortfall | EDUCATION | fraudulent | yes | Fraud via an inconsistent quantity/amount (request for 54 tablets vs 31 recorded in the asset register); no red-flag keywords. |
| V3T-044 | patient_and_record_crossing | MEDICAL | fraudulent | no | Fraud via a contradiction between the campaign and its documents (pharmacy ledger is for a different patient and file). |
| V3T-084 | family_cost_share_unclear | MEDICAL | borderline | no | Borderline: preliminary estimate with family contribution and net balance unconfirmed; frozen V3 approves this group (unsafe-approval test). |
| V3T-194 | account_image_without_issue_date | EDUCATION | borderline | yes | Borderline: cropped account screenshot without issue date or registrar seal; no red-flag keywords; frozen V3 approves this group. |
| V3T-224 | compost_route_cold_store | COMMUNITY | legitimate | no | Legitimate community project whose wording matches known fraud lexicons (false-positive stress test). |
| V3T-104 | accessible_exam_studio | EDUCATION | legitimate | yes | Legitimate education access costs with a matching invoice and registration record; no red-flag keywords. |
| V3T-024 | island_burn_recovery | MEDICAL | legitimate | yes | Legitimate medical rehabilitation with unusual travel and lodging costs justified by a separate quote. |
| E150-102 | hill_footpath_lighting | COMMUNITY | legitimate | yes | Legitimate community project with incomplete supporting evidence (preliminary record; final authorization stamp still being processed). |

Source corpora (read-only): `final_test_scenarios_v3.jsonl` (31f16ae955c4), `independent_test_150.jsonl` (099016d5da87).

## 3. Frozen code and dataset integrity

* Git commit before the run: `ac1e29bab3c86643e7dda7ff9f98bc3be1642617`; working tree clean: True.
* 46 files (evaluation framework, production prompt path, RAG, Gemini client, config, schemas, fraud rules, frozen V3, approval workflow, datasets, selection) unchanged after the run: **False** — changed: ['evaluation/report_gemini_eval_v1.py'].
* Files that executed during the run (all except this read-only report generator) unchanged: **True**. The report generator was corrected after the run so that frozen V3 is re-run offline for every case (it had read V3's decision from the combined-system record, which is missing when Gemini failed); the recomputed V3 decisions match every recorded one (section 8).
* Production default model (no override): `gemini-3.8-flash`; evaluation model (process-only override): `gemini-3.6-flash`.

## 4. API usage and quota

| Stage | Used | Approved budget |
|---|---:|---:|
| Generation | 20 | 20 |
| Embedding | 10 | 10 |

Each counted call is exactly one HTTP request (no automatic retries); 6 s pacing; free-tier quota (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 20 per day for this model).

## 5. Model reliability and latency

| Sample | Model | Generation succeeded | Timeouts | Server errors | Mean latency | p95 latency |
|---|---|---:|---:|---:|---:|---:|
| Earlier 3-case pilot (V3T-071/131/201) | gemini-3.8-flash | 1/6 | 3 | 2 | 174.81 s | 174.81 s |
| Earlier 3-case pilot (V3T-071/131/201) | gemini-3.6-flash | 6/6 | 0 | 0 | 21.94 s | 30.03 s |
| **This evaluation (10 new groups)** | gemini-3.6-flash | 19/20 | 0 | 1 | 45.5 s | 72.5 s |

This evaluation: median 45.1 s, max 72.5 s over 19 successful responses; embedding requests [0.97, 0.68, 0.64, 5.93, 0.49, 0.68, 0.88, 0.76, 0.75, 0.72] s. The earlier pilots used different cases and are reported separately; they are not pooled.

## 6. Case-by-case predictions

| Case | Label | Fallback | Gemini no-docs | Gemini + RAG | V3 | Combined | Combined workflow state | RAG latency |
|---|---|---|---|---|---|---|---|---:|
| V3T-064 | fraudulent | APPROVED | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | APPROVED | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 39.98 s |
| V3T-244 | fraudulent | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | REJECTED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 46.22 s |
| V3T-154 | fraudulent | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 51.3 s |
| V3T-044 | fraudulent | APPROVED | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 34.57 s |
| V3T-084 | borderline | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | APPROVED | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 17.85 s |
| V3T-194 | borderline | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | APPROVED | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 38.94 s |
| V3T-224 | legitimate | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | APPROVED | APPROVED | APPROVED | ELIGIBLE_PENDING_CONFIRMATION | 72.48 s |
| V3T-104 | legitimate | APPROVED | NEEDS_MORE_INFORMATION | NOT_RUN | APPROVED | NOT_RUN | — | — s |
| V3T-024 | legitimate | APPROVED | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | APPROVED | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 51.33 s |
| E150-102 | legitimate | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | 53.65 s |

### Explanations and evidence

**V3T-064** (fraudulent, internally_consistent_but_forged_clinic_file)

* Retrieved evidence (embedding score): Treatment cost schedule (0.7933), Specialty service note (0.7508)
* Gemini + RAG — risk MEDIUM: The campaign requests ₹2,31,250 for a continuing care package supported by cost estimates and consultant notes referencing patient record QX-0034. However, the documents cite a future date of September 2026 and lack a specific medical diagnosis or attending physician details.
  * Red flags: ['Retrieved document evidence contains a future date (07 September 2026)', 'Lack of specific medical diagnosis beyond generic monitoring and supportive therapy', 'Hospital name lacks verifiable local context for Chitradurga area']; missing: ['Detailed clinical diagnosis and diagnostic test reports', 'Attending physician signature and medical registration details', 'Government-issued identification for beneficiary verification']
* Gemini without documents: The campaign seeks ₹2,31,250 for a continuing care package but fails to provide a specific medical diagnosis, treating clinician details, or supporting documents. Verification of medical necessity and hospital estimates is required before proceeding.
* V3 findings: —; V3 reasons: ['Critical claim and identity evidence are present and no material contradiction was found.', 'Optional supporting records are incomplete; this did not block approval.']
* Combined: escalated by Gemini: True; API errors: none

**V3T-244** (fraudulent, supplier_ledger_closed)

* Retrieved evidence (embedding score): Contractor payment record (0.6852)
* Gemini + RAG — risk HIGH: The campaign seeks ₹2,31,250 to settle an unpaid contractor invoice for flood steps in Chitradurga. However, retrieved financial evidence indicates that the invoice has already been fully paid by bank transfer and the account is closed, presenting a direct contradiction and significant fraud risk.
  * Red flags: ['Campaign pitch claims the invoice is unpaid, contradicting retrieved records showing the balance is nil and paid in full', 'Zero documents uploaded directly by the campaign organizer to substantiate an outstanding debt']; missing: ['Certified unpaid invoice or bill from the masonry contractor', 'Official financial statement showing pending liabilities from Chitradurga Shared Services Association', 'Contract or work order for the Chitradurga flood steps project']
* Gemini without documents: The campaign requests ₹2,31,250 to settle an unpaid masonry invoice for flood steps on behalf of an organization. However, zero supporting documents such as contractor invoices, work orders, or organizational registration were provided to verify the claim.
* V3 findings: —; V3 reasons: ['Critical evidence missing: A record links the named beneficiary to the campaign.']
* Combined: escalated by Gemini: True; API errors: none

**V3T-154** (fraudulent, equipment_dispatch_shortfall)

* Retrieved evidence (embedding score): Learning lab asset register (0.743)
* Gemini + RAG — risk HIGH: The campaign requests funds for 54 tablets for a shared learning lab in Chitradurga, but lists an individual as the beneficiary rather than the institution. Additionally, retrieved documentation only records 31 tablets received, creating a discrepancy with the requested total.
  * Red flags: ['Individual beneficiary account listed for institutional facility equipment', 'Discrepancy between campaign claim of 54 tablets and retrieved log showing 31 tablets', 'No verified institutional documents attached by the campaigner']; missing: ['Official authorization letter from Blue Courtyard Learning Lab', 'Vendor quotation or purchase order for 54 tablets', 'Institutional bank account or organizational registration proof']
* Gemini without documents: The requested budget of ₹2,31,250 for 54 tablets (~₹4,282 per tablet) is financially plausible for basic educational devices. However, the campaign provides zero supporting documents, lacks official verification for the Blue Courtyard Learning Lab, and lists an individual beneficiary for a shared community initiative.
* V3 findings: ['CAMPAIGN_DOCUMENT_QUANTITY_CONFLICT']; V3 reasons: ['A material inconsistency requires human review; this is not an automatic fraud finding.', "The campaign requests 54 tablets, but 'Learning lab asset register' records 31 tablets."]
* Combined: escalated by Gemini: False; API errors: none

**V3T-044** (fraudulent, patient_and_record_crossing)

* Retrieved evidence (embedding score): Specialist discharge record (0.8091), Pharmacy ledger copy (0.7755)
* Gemini + RAG — risk HIGH: The campaign requests ₹2,31,250 for medication release, but the attached pharmacy ledger providing this exact amount belongs to a different patient (Lina Mathew). Additionally, the campaign pitch lacks a specific diagnosis, line-item breakdown, and treating doctor details for Omar Jacob.
  * Red flags: ['Pharmacy debit note matching the requested amount belongs to a different patient (Lina Mathew, File HX-0094) instead of Omar Jacob', 'Campaign story lacks specific medical diagnosis and treating doctor details', 'No verified cost estimate provided for patient Omar Jacob']; missing: ['Official hospital cost estimate or pharmacy invoice issued specifically for Omar Jacob', 'Detailed medical prescription and diagnosis signed by a registered practitioner', 'Government-issued identification proof for the beneficiary']
* Gemini without documents: The campaign requests ₹2,31,250 for a specialist medication package but provides zero supporting medical documentation. While a patient file reference and hospital name are stated, there is no diagnosis, treating doctor information, or itemized cost estimate.
* V3 findings: ['IDENTITY_MISMATCH']; V3 reasons: ['A material inconsistency requires human review; this is not an automatic fraud finding.', "'Pharmacy ledger copy' is in a different person's name (no part of the name is shared)."]
* Combined: escalated by Gemini: False; API errors: none

**V3T-084** (borderline, family_cost_share_unclear)

* Retrieved evidence (embedding score): Preliminary treatment estimate (0.801)
* Gemini + RAG — risk MEDIUM: The requested amount of ₹2,31,250 is plausible for oncology care in India, and an estimate reference was retrieved. However, the campaign narrative is extremely minimal and lacks specific diagnostic details, a treating clinician, and confirmed net financial need.
  * Red flags: ['Vague campaign pitch with no detailed diagnosis or treatment plan', 'Net payable balance after insurance or family contribution is unconfirmed', 'No official government identity proof uploaded']; missing: ['Detailed diagnostic report and doctor treatment advice', 'Verified government ID proof of Omar Jacob', 'Confirmed net hospital bill or formal financial estimate statement from hospital billing']
* Gemini without documents: The campaign requests ₹2,31,250 for oncology care but lacks basic clinical details such as a specific diagnosis, attending physician, and confirmed net treatment expenses. Without any attached medical records or hospital estimates, the request currently cannot be verified.
* V3 findings: —; V3 reasons: ['Critical claim and identity evidence are present and no material contradiction was found.', 'Optional supporting records are incomplete; this did not block approval.']
* Combined: escalated by Gemini: True; API errors: none

**V3T-194** (borderline, account_image_without_issue_date)

* Retrieved evidence (embedding score): Cropped workshop account screenshot (0.8787)
* Gemini + RAG — risk HIGH: The campaign requests ₹2,31,250 for workshop material charges at North Loop Technical College for student Omar Jacob. However, the supporting evidence consists only of a cropped screenshot that lacks essential validation elements like an issue date, official letterhead, and registrar endorsement. Verified fee documentation and proof of enrollment are required before proceeding.
  * Red flags: ['Cropped account screenshot lacks a visible issue date and official registrar endorsement', 'Substantial material fee requested without an itemized breakdown or formal institutional fee letter']; missing: ['Official fee demand notice or fee structure stamped and signed by the college registrar', 'Valid student ID card or official proof of enrollment from North Loop Technical College', 'Itemized breakdown of the workshop materials included in the charge']
* Gemini without documents: The campaign requests ₹2,31,250 for technical college workshop materials but provides no verified documentation. The pitch relies on an unverified fee claim lacking an official seal or issue date, requiring verified institutional proof before proceeding.
* V3 findings: —; V3 reasons: ['Critical claim and identity evidence are present and no material contradiction was found.', 'Optional supporting records are incomplete; this did not block approval.']
* Combined: escalated by Gemini: True; API errors: none

**V3T-224** (legitimate, compost_route_cold_store)

* Retrieved evidence (embedding score): Supplier's itemized project quotation (0.8072), Cooperative works authorization (0.7705)
* Gemini + RAG — risk LOW: The campaign presents a clear, realistic community infrastructure request for a compost sorting canopy in Chitradurga. Retrieved supplier quotes and work authorization directly support the target amount of ₹2,31,250 with consistent details.
  * Red flags: —; missing: ['Organizational registration documents for Chitradurga Shared Services Association', 'Verified bank account details for organizational payout']
* Gemini without documents:  The community project proposal for a waste-sorting canopy in Chitradurga is budget-plausible and geographically specific. However, no fabricator quotes or organizational registration documents were provided to verify the claim.
* V3 findings: —; V3 reasons: ['Critical claim and identity evidence are present and no material contradiction was found.', 'Optional supporting records are incomplete; this did not block approval.']
* Combined: escalated by Gemini: False; API errors: none

**V3T-104** (legitimate, accessible_exam_studio)

* Retrieved evidence (embedding score): Candidate access invoice (0.8681), Current registration record (0.7918)
* Gemini + RAG — risk None: —
  * Red flags: —; missing: —
* Gemini without documents: The campaign requests ₹2,31,250 for examination access tools and invigilator support under the Education category. However, zero supporting documents or official fee structures from the Mosaic Examination Board have been provided to verify these high costs.
* V3 findings: —; V3 reasons: ['—']
* Combined: escalated by Gemini: None; API errors: ['gemini_rag:generation:SERVER_ERROR']

**V3T-024** (legitimate, island_burn_recovery)

* Retrieved evidence (embedding score): Access route and lodging quote (0.8014), Rehabilitation attendance plan (0.7983)
* Gemini + RAG — risk MEDIUM: The campaign requests ₹2,31,250 for travel and lodging for burn scar recovery sessions. While retrieved quotes match the exact financial target and name the patient, the reference to a water crossing and 'Bay District Rehabilitation Service' for a resident of landlocked Chitradurga presents geographical inconsistencies, and primary medical diagnosis records are missing.
  * Red flags: ['Geographical and institutional naming mismatch (Chitradurga is landlocked, yet pitch references a water crossing to Bay District Rehabilitation Service)', 'Lack of formal medical diagnosis records or doctor-signed clinical certificates']; missing: ['Primary medical diagnosis report or burn treatment discharge summary', 'Official estimate on facility letterhead signed by a licensed treating clinician', 'Government-issued identification proof of the beneficiary']
* Gemini without documents: The campaign requests ₹2,31,250 for travel and lodging to 'Bay District Rehabilitation Service' involving a water crossing, which appears geographically inconsistent with Chitradurga, Karnataka. Additionally, zero supporting medical documents or cost estimates were provided to verify the claim.
* V3 findings: —; V3 reasons: ['Critical claim and identity evidence are present and no material contradiction was found.', 'Optional supporting records are incomplete; this did not block approval.']
* Combined: escalated by Gemini: True; API errors: none

**E150-102** (legitimate, hill_footpath_lighting)

* Retrieved evidence (embedding score): Preliminary record Q41-02 (0.7055)
* Gemini + RAG — risk MEDIUM: The community lighting project in Udaipur has a plausible budget and matching preliminary records including village minutes and installer quotes. However, the final official authorization is still pending and funds are directed to an individual beneficiary for civic work.
  * Red flags: ['Individual beneficiary listed for public community infrastructure work', 'Final authorization stamp from municipal or cooperative authorities is still pending']; missing: ['Final signed authorization or NOC from local authorities/electricity cooperative', 'Community or institutional bank account details for civic works execution']
* Gemini without documents: The campaign seeks funding for public footpath lighting in Udaipur submitted under an individual beneficiary profile without municipal approval or vendor quotations. With zero supporting documents provided, the project lacks official authorization and verified cost estimates.
* V3 findings: —; V3 reasons: ['Critical evidence missing: A record links the named beneficiary to the campaign.']
* Combined: escalated by Gemini: True; API errors: none

## 7. Confusion matrices and outcome counts

Detection = FLAG_FOR_REVIEW or REJECTED. NEEDS_MORE_INFORMATION and approval held pending confirmation are not detections. Negatives = 4 legitimate + 2 borderline.

| System | TP | FP | FN | TN | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Heuristics, no documents | 4 | 6 | 0 | 0 | 40% (17–69%) | 100% (51–100%) | 57% | 100% (61–100%) |
| Deterministic fallback (heuristics + lexical retrieval) | 2 | 4 | 2 | 2 | 33% (10–70%) | 50% (15–85%) | 40% | 67% (30–90%) |
| Gemini 3.6 Flash, no documents | 0 | 0 | 4 | 6 | n/a | 0% (0–49%) | n/a | 0% (0–39%) |
| Gemini 3.6 Flash + RAG | 3 | 0 | 1 | 6 | 100% (44–100%) | 75% (30–95%) | 86% | 0% (0–39%) |
| Frozen V3 | 2 | 0 | 2 | 6 | 100% (34–100%) | 50% (15–85%) | 67% | 0% (0–39%) |
| Frozen V3 + Gemini (combined) | 4 | 4 | 0 | 2 | 50% (22–78%) | 100% (51–100%) | 67% | 67% (30–90%) |

| Outcome | Heuristics, no documents | Deterministic fallback (heuristics + lexical retrieval) | Gemini 3.6 Flash, no documents | Gemini 3.6 Flash + RAG | Frozen V3 | Frozen V3 + Gemini (combined) |
|---|---:|---:|---:|---:|---:|---:|
| Fraud-specific review flags (fraud → FLAG) | 4 | 2 | 0 | 2 | 2 | 4 |
| Rejections (all labels) | 0 | 0 | 0 | 1 | 0 | 0 |
| Information requests (legit / fraud / borderline) | 0/0/0 | 0/0/0 | 4/4/2 | 2/1/2 | 1/1/0 | 0/0/0 |
| Approved → held pending confirmation (legit / fraud / borderline) | 0/0/0 | 2/2/0 | 0/0/0 | 1/0/0 | 3/1/2 | 1/0/0 |
| Legitimate unnecessarily escalated (FLAG/REJECT) | 4 | 2 | 0 | 0 | 0 | 2 |
| Legitimate sent for more information | 0 | 0 | 4 | 2 | 1 | 0 |
| Fraud missed: approved then held | 0 | 2 | 0 | 0 | 1 | 0 |
| Fraud missed: information request | 0 | 0 | 4 | 1 | 1 | 0 |
| Not run / runtime or API failure (all labels) | 0 | 0 | 0 | 1 | 0 | 1 |

Three-class decision matrices:

*Heuristics, no documents*: legitimate: {'FLAG_FOR_REVIEW': 4}; fraudulent: {'FLAG_FOR_REVIEW': 4}; borderline: {'FLAG_FOR_REVIEW': 2}
*Deterministic fallback (heuristics + lexical retrieval)*: legitimate: {'FLAG_FOR_REVIEW': 2, 'APPROVED': 2}; fraudulent: {'APPROVED': 2, 'FLAG_FOR_REVIEW': 2}; borderline: {'FLAG_FOR_REVIEW': 2}
*Gemini 3.6 Flash, no documents*: legitimate: {'NEEDS_MORE_INFORMATION': 4}; fraudulent: {'NEEDS_MORE_INFORMATION': 4}; borderline: {'NEEDS_MORE_INFORMATION': 2}
*Gemini 3.6 Flash + RAG*: legitimate: {'APPROVED': 1, 'NOT_RUN': 1, 'NEEDS_MORE_INFORMATION': 2}; fraudulent: {'NEEDS_MORE_INFORMATION': 1, 'REJECTED': 1, 'FLAG_FOR_REVIEW': 2}; borderline: {'NEEDS_MORE_INFORMATION': 2}
*Frozen V3*: legitimate: {'APPROVED': 3, 'NEEDS_MORE_INFORMATION': 1}; fraudulent: {'APPROVED': 1, 'NEEDS_MORE_INFORMATION': 1, 'FLAG_FOR_REVIEW': 2}; borderline: {'APPROVED': 2}
*Frozen V3 + Gemini (combined)*: legitimate: {'APPROVED': 1, 'NOT_RUN': 1, 'FLAG_FOR_REVIEW': 2}; fraudulent: {'FLAG_FOR_REVIEW': 4}; borderline: {'FLAG_FOR_REVIEW': 2}

## 8. Error and disagreement analysis

API failures: V3T-104 gemini_rag generation SERVER_ERROR.

| Case | Label | Pair | A | B |
|---|---|---|---|---|
| V3T-064 | fraudulent | gemini_rag vs heuristics_lexical | NEEDS_MORE_INFORMATION | APPROVED |
| V3T-064 | fraudulent | gemini_rag vs v3 | NEEDS_MORE_INFORMATION | APPROVED |
| V3T-064 | fraudulent | hybrid vs v3 | FLAG_FOR_REVIEW | APPROVED |
| V3T-244 | fraudulent | gemini_rag vs heuristics_lexical | REJECTED | FLAG_FOR_REVIEW |
| V3T-244 | fraudulent | gemini_rag vs v3 | REJECTED | NEEDS_MORE_INFORMATION |
| V3T-244 | fraudulent | gemini_rag vs gemini_no_rag | REJECTED | NEEDS_MORE_INFORMATION |
| V3T-244 | fraudulent | hybrid vs v3 | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| V3T-154 | fraudulent | gemini_rag vs gemini_no_rag | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| V3T-044 | fraudulent | gemini_rag vs heuristics_lexical | FLAG_FOR_REVIEW | APPROVED |
| V3T-044 | fraudulent | gemini_rag vs gemini_no_rag | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| V3T-084 | borderline | gemini_rag vs heuristics_lexical | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW |
| V3T-084 | borderline | gemini_rag vs v3 | NEEDS_MORE_INFORMATION | APPROVED |
| V3T-084 | borderline | hybrid vs v3 | FLAG_FOR_REVIEW | APPROVED |
| V3T-194 | borderline | gemini_rag vs heuristics_lexical | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW |
| V3T-194 | borderline | gemini_rag vs v3 | NEEDS_MORE_INFORMATION | APPROVED |
| V3T-194 | borderline | hybrid vs v3 | FLAG_FOR_REVIEW | APPROVED |
| V3T-224 | legitimate | gemini_rag vs heuristics_lexical | APPROVED | FLAG_FOR_REVIEW |
| V3T-224 | legitimate | gemini_rag vs gemini_no_rag | APPROVED | NEEDS_MORE_INFORMATION |
| V3T-104 | legitimate | gemini_rag vs heuristics_lexical | NOT_RUN | APPROVED |
| V3T-104 | legitimate | gemini_rag vs v3 | NOT_RUN | APPROVED |
| V3T-104 | legitimate | gemini_rag vs gemini_no_rag | NOT_RUN | NEEDS_MORE_INFORMATION |
| V3T-104 | legitimate | hybrid vs v3 | NOT_RUN | APPROVED |
| V3T-024 | legitimate | gemini_rag vs heuristics_lexical | NEEDS_MORE_INFORMATION | APPROVED |
| V3T-024 | legitimate | gemini_rag vs v3 | NEEDS_MORE_INFORMATION | APPROVED |
| V3T-024 | legitimate | hybrid vs v3 | FLAG_FOR_REVIEW | APPROVED |
| E150-102 | legitimate | gemini_rag vs heuristics_lexical | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW |
| E150-102 | legitimate | hybrid vs v3 | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |

Why the combined system escalated beyond V3 (the frozen hybrid rule escalates on Gemini's decision *or* on any red flag Gemini attaches, even to an information request):

| Case | Label | V3 | Gemini + RAG decision | Gemini red flags | Trigger |
|---|---|---|---|---:|---|
| V3T-064 | fraudulent | APPROVED | NEEDS_MORE_INFORMATION | 3 | red_flags_only |
| V3T-244 | fraudulent | NEEDS_MORE_INFORMATION | REJECTED | 2 | gemini_decision |
| V3T-084 | borderline | APPROVED | NEEDS_MORE_INFORMATION | 3 | red_flags_only |
| V3T-194 | borderline | APPROVED | NEEDS_MORE_INFORMATION | 2 | red_flags_only |
| V3T-024 | legitimate | APPROVED | NEEDS_MORE_INFORMATION | 2 | red_flags_only |
| E150-102 | legitimate | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | 2 | red_flags_only |

Frozen V3 re-run offline for this report matches the V3 decision recorded inside every combined-system result: **True** (9 cases).

Computed answers to the contribution questions:

1. Fraud flagged by Gemini + RAG but not by V3: ['V3T-244']; not by the deterministic fallback: ['V3T-044'].
2. Correct direction with RAG only: ['V3T-244', 'V3T-154', 'V3T-044', 'V3T-224']; without documents only: none; both: 2 cases.
3. Legitimate cases flagged by Gemini + RAG: none.
4. Internally consistent fabricated fraud: {'V3T-064': 'NEEDS_MORE_INFORMATION'}.
5. Unsafe approvals (fraud or borderline APPROVED): Frozen V3 ['V3T-064', 'V3T-084', 'V3T-194']; Frozen V3 + Gemini (combined) none; Gemini 3.6 Flash + RAG none; Deterministic fallback (heuristics + lexical retrieval) ['V3T-064', 'V3T-044']. Manual reviews: Heuristics, no documents 10; Deterministic fallback (heuristics + lexical retrieval) 6; Gemini 3.6 Flash, no documents 0; Gemini 3.6 Flash + RAG 2; Frozen V3 2; Frozen V3 + Gemini (combined) 8.
6. Latency: mean 45.5 s, p95 72.5 s per Gemini verification.

## 9. Evidence-retrieval analysis

| Case | Docs retrieved (embedding score) | Lexical retrieves same documents |
|---|---|---|
| V3T-064 | Treatment cost schedule (0.7933), Specialty service note (0.7508) | True |
| V3T-244 | Contractor payment record (0.6852) | True |
| V3T-154 | Learning lab asset register (0.743) | True |
| V3T-044 | Specialist discharge record (0.8091), Pharmacy ledger copy (0.7755) | True |
| V3T-084 | Preliminary treatment estimate (0.801) | True |
| V3T-194 | Cropped workshop account screenshot (0.8787) | True |
| V3T-224 | Supplier's itemized project quotation (0.8072), Cooperative works authorization (0.7705) | True |
| V3T-104 | Candidate access invoice (0.8681), Current registration record (0.7918) | True |
| V3T-024 | Access route and lodging quote (0.8014), Rehabilitation attendance plan (0.7983) | True |
| E150-102 | Preliminary record Q41-02 (0.7055) | True |

Every case has one or two short documents, so any retriever returns all of them. Successful retrieval here shows the pipeline works; it is **not** evidence of relevance ranking quality, which needs gold evidence annotations (protocol v4).

## 10. Limitations and statistical uncertainty

* 10 cases, one per scenario group: 4 fraud, 4 legitimate, 2 borderline. Wilson intervals above are wide; a single case moves recall by 25 points. No difference between systems here is statistically meaningful.
* Previously available synthetic data from earlier development cycles; single author; template-generated groups; the 150-case source was used to motivate V2/V3. This is diagnostic testing, not independent validation.
* Each configuration was run once; Gemini output is non-deterministic (temperature 0.1), so repeat runs could differ.
* Gemini's decisions use the production prompt; red flags attached to an information request are not counted as detections here (the production router would mark such campaigns FLAGGED).
* Holding a campaign pending confirmation is not fraud detection; whether external confirmation would stop a pending fraud is unmeasured.

## 11. Interpretation and recommendation

### Interpretation

*Written after reviewing the machine-generated sections above. The sample has 10 cases, one per scenario
group, so every statement below is a diagnostic observation and not an accuracy estimate.*

**Reliability.**
- 19 of 20 generation calls succeeded (Wilson 95% interval 76–99%). The one failure was a single HTTP 503,
  with no timeouts. That is much better than 3.8 Flash in the earlier pilot (1/6), but it does not yet
  establish the ≥95% success rate the go criterion requires.
- Latency roughly doubled compared with the 3-case pilot: a mean of 45.5 s and a p95 of 72.5 s, against
  21.9 s and 30.0 s. That is too slow for a synchronous check during campaign submission. It would be
  workable only as an asynchronous background check.

**Grounded contributions from documents.**
- Document-grounded Gemini moved four cases in the correct direction compared with Gemini without
  documents: V3T-244, V3T-154, V3T-044 and V3T-224. No case moved the other way.
- Without documents, Gemini returned NEEDS_MORE_INFORMATION for all 10 cases.
- Its explanations cite the retrieved evidence. On V3T-244 it found that the "unpaid" invoice was already
  paid and the supplier account closed, a contradiction frozen V3 missed (V3 sent the case for more
  information instead). On V3T-044 it found the ledger was in a different patient's name, which V3 also
  caught.
- By its own decision, Gemini + RAG flagged **no** legitimate campaign and approved no fraudulent or
  borderline campaign. It returned one rejection (V3T-244), which the combined design caps at manual
  review.

**What Gemini did not do.**
- **The internally consistent fabricated dossier (V3T-064) was not detected.** Gemini asked for more
  information, citing an alleged "future date (07 September 2026)", a missing diagnosis and an
  unfamiliar hospital.
  - The date flag is spurious: the production prompt gives the model no current date.
  - The other two flags are generic.
  - Nothing in the dossier reveals the fabrication, so this remains the case only external confirmation
    can settle.
- One retrieval check (V3T-104) failed with a 503 and was not retried, because the budget was fully used.
  A deployed combined system would treat that as a verification error and never as an approval.

**The combined system's 4/4 recall comes partly from its escalation rule, not only from detection.**
- The frozen rule escalates to manual review whenever Gemini attaches any red flag, even to an
  information request. Five of its six escalations beyond V3 came from red flags alone:
  - one fabricated-fraud case, caught for partly spurious reasons;
  - the two borderline cases, which were appropriate to escalate since V3 had approved both;
  - two legitimate campaigns.
- One of those legitimate escalations (V3T-024) rests on a real flaw in the synthetic data. The generator
  swapped a coastal story onto a landlocked city, and Gemini noticed. It is counted as a false positive
  against the label, but it is a defect in the data rather than the model.
- Net effect against frozen V3:
  - unsafe approvals of fraudulent or borderline cases fell from 3 to 0;
  - legitimate escalations rose from 0 to 2;
  - manual reviews rose from 2 to 8 of 10.

That is a large workload increase for a small sample.

**The deterministic fallback remains weak.** The production fallback (heuristics with lexical retrieval)
approved two fraudulent cases (V3T-064, V3T-044) and escalated two legitimate ones.

### Recommendation

**Gemini 3.6 Flash merits a larger evaluation, but not the full 180-call run as currently configured, and
not a production change.** Grounded detection of a contradiction V3 missed, no Gemini-initiated
escalation of legitimate campaigns, and correct use of retrieved documents justify further testing.
Three issues should be settled first, each needing the owner's decision:

1. **Pre-register the combined escalation rule.**
   - The current rule escalates on any Gemini red flag.
   - A post-hoc alternative escalates only on Gemini's FLAG or REJECT, and otherwise downgrades to
     NEEDS_MORE_INFORMATION; it would not approve when Gemini asks for more information.
   - Re-reading the saved outputs suggests this alternative would keep zero unsafe approvals and zero
     legitimate escalations at 3/4 recall. **That is a hypothesis formed after seeing these results**, so
     it must be fixed in advance and tested on new cases, not scored on these ones.
2. **Decide whether the evaluation may use a prompt that states the current date.** This changes the
   production prompt path, so the owner must approve it. Without the date, any document dated after the
   model's internal "now" can draw a spurious flag.
3. **Run the next stage on cases that have not been inspected,** preferably an early tranche of the
   protocol v4 independent set, as an asynchronous check with latency recorded. The 300-case synthetic
   corpus has now been used for V3 development, the final test, two pilots and this evaluation.

**Keep the production default model unchanged** until a pre-registered evaluation on new cases confirms
reliability (≥95% success) and acceptable latency. Keep the independent-confirmation requirement in every
configuration: none of these results justify activating a campaign or releasing funds on model judgement
alone.
