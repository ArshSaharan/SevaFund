# Group-level analysis of V2/V3 synthetic results

Saved predictions only; no verifier was executed. Cases inside a scenario family share a template, so the label cluster (family × label) is the unit. Cluster-level rates count each cluster once (majority outcome); cluster-bootstrap intervals resample clusters. Fraud is positive; legitimate and borderline are negatives here (the V3 runner's own reports excluded borderline — FPR differs only if borderline cases are flagged, which they were not).

## final_test_300

300 cases in 30 label clusters.

| Measure | V2 | V3 |
|---|---:|---:|
| Homogeneous clusters (all cases same decision) | 30/30 | 30/30 |
| Detection ICC | 1.0 | 1.0 |
| Effective sample size (detection) | 30.0 | 30.0 |
| Recall — case level, naive Wilson CI | 50.0% (40–60%) | 60.0% (50–69%) |
| Recall — cluster bootstrap CI | 50.0% (20–80%) | 60.0% (30–90%) |
| Fraud clusters flagged | 5/10 (24–76%) | 6/10 (31–83%) |
| Fraud clusters auto-approved | 0/10 (0–28%) | 2/10 (6–51%) |
| Legitimate clusters approved | 0/10 (0–28%) | 10/10 (72–100%) |
| Legitimate clusters flagged | 0/10 (0–28%) | 0/10 (0–28%) |
| Borderline clusters approved | 0/10 (0–28%) | 2/10 (6–51%) |
| Fraud auto-approval — cluster bootstrap CI | 0.0% (0–0%) | 20.0% (0–50%) |

**Under the pending-confirmation workflow** (automated APPROVED → ELIGIBLE_PENDING_CONFIRMATION):

| | V2 | V3 |
|---|---:|---:|
| Safety: automatic activations | 0 | 0 |
| Safety: fraud detected (review/reject) | 50 | 60 |
| Safety: fraud held pending external confirmation | 0 | 20 |
| Safety: borderline held pending confirmation | 0 | 20 |
| Workload: manual reviews | 50 | 60 |
| Workload: information requests | 250 | 100 |
| Workload: external confirmations required | 0 | 420 |
| Workload: avoidable legitimate friction (NMI/review/error) | 100 | 0 |

Sensitivity (assumption, not a measurement): expected fraudulent activations if external confirmation misses a share of pending fraud — V3: {"5%": 1.0, "20%": 4.0, "50%": 10.0}

Per-cluster outcomes (V3):

| Cluster | Label | Size | V3 majority decision | V2 majority decision |
|---|---|---:|---|---|
| accessible_exam_studio | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| account_image_without_issue_date | borderline | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| archival_language_keyboard | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| coastal_access_permit_unissued | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| committee_minutes_unratified | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| compost_route_cold_store | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| consistent_bursary_papers_forged | fraudulent | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| credential_calendar_shortfall | fraudulent | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| dispatch_quantity_diverges | fraudulent | 10 | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| earthquake_masonry_repair | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| enzyme_cold_chain | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| equipment_dispatch_shortfall | fraudulent | 10 | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| false_provenance_project_alignment | fraudulent | 10 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW |
| family_cost_share_unclear | borderline | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| field_research_recordings | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| grant_installment_unposted | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| home_ventilation_backup | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| internally_consistent_but_forged_clinic_file | fraudulent | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| island_burn_recovery | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| market_food_cooling_room | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| orthotic_refitting | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| paid_term_balance_reused | fraudulent | 10 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW |
| partner_share_not_confirmed | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| patient_and_record_crossing | fraudulent | 10 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW |
| patient_link_not_in_extract | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| seat_held_until_practical | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| supplier_ledger_closed | fraudulent | 10 | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW |
| supplier_quote_expires_soon | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| trial_slot_authorization_pending | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| unrelated_account_recipient | fraudulent | 10 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW |

## v3_development_180

180 cases in 18 label clusters.

| Measure | V2 | V3 |
|---|---:|---:|
| Homogeneous clusters (all cases same decision) | 18/18 | 18/18 |
| Detection ICC | 1.0 | 1.0 |
| Effective sample size (detection) | 18.0 | 18.0 |
| Recall — case level, naive Wilson CI | 16.7% (9–28%) | 50.0% (38–62%) |
| Recall — cluster bootstrap CI | 16.7% (0–50%) | 50.0% (17–83%) |
| Fraud clusters flagged | 1/6 (3–56%) | 3/6 (19–81%) |
| Fraud clusters auto-approved | 0/6 (0–39%) | 3/6 (19–81%) |
| Legitimate clusters approved | 0/6 (0–39%) | 6/6 (61–100%) |
| Legitimate clusters flagged | 0/6 (0–39%) | 0/6 (0–39%) |
| Borderline clusters approved | 0/6 (0–39%) | 0/6 (0–39%) |
| Fraud auto-approval — cluster bootstrap CI | 0.0% (0–0%) | 50.0% (17–83%) |

**Under the pending-confirmation workflow** (automated APPROVED → ELIGIBLE_PENDING_CONFIRMATION):

| | V2 | V3 |
|---|---:|---:|
| Safety: automatic activations | 0 | 0 |
| Safety: fraud detected (review/reject) | 10 | 30 |
| Safety: fraud held pending external confirmation | 0 | 30 |
| Safety: borderline held pending confirmation | 0 | 0 |
| Workload: manual reviews | 10 | 30 |
| Workload: information requests | 170 | 60 |
| Workload: external confirmations required | 0 | 270 |
| Workload: avoidable legitimate friction (NMI/review/error) | 60 | 0 |

Sensitivity (assumption, not a measurement): expected fraudulent activations if external confirmation misses a share of pending fraud — V3: {"5%": 1.5, "20%": 6.0, "50%": 15.0}

Per-cluster outcomes (V3):

| Cluster | Label | Size | V3 majority decision | V2 majority decision |
|---|---|---:|---|---|
| access_design_practicum | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| beneficiary_record_divergence | fraudulent | 10 | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW |
| care_supply_request_unlinked | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| coherent_but_fabricated_dossier | fraudulent | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| conditional_lab_seat | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| home_cardiac_monitoring | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| informal_heat_shelter | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| internally_aligned_false_project | fraudulent | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| internally_consistent_enrollment_and_invoice | fraudulent | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| marine_apprentice_block | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| mobile_market_reading_cart | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| preauthorization_waiting | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| remote_neurology_rehab | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| shoreline_permit_pending | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| sponsor_credit_uncertain | borderline | 10 | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION |
| teaching_period_mismatch | fraudulent | 10 | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| tidal_pump_retrofit | legitimate | 10 | APPROVED | NEEDS_MORE_INFORMATION |
| vendor_beneficiary_count | fraudulent | 10 | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
