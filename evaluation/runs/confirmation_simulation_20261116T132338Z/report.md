# External-confirmation workflow — SIMULATION (not a measurement)

All figures follow from the assumed contact behaviour listed under each scenario. They test the workflow's logic and show which assumptions drive safety and workload; they say nothing about real institutions or verifiers. Replace the assumptions with confirmation-pilot data (`evaluation/confirmation_pilot_protocol.md`).

Mean over replications, with the 2.5–97.5 percentile range in brackets.

## Population: final_test_300

Campaigns entering confirmation: 140 ({'legitimate': 100, 'fraudulent': 20, 'borderline': 20}). Replications per scenario: 500.

| Metric | reference | careful_verifiers | low_responsiveness | adversarial |
|---|---:|---:|---:|---:|
| fraud prevented from activation (rate) | 0.992 [0.95–1] | 0.995 [0.95–1] | 0.993 [0.95–1] | 0.898 [0.75–1] |
| fraud activated (campaigns) | 0.17 [0–1] | 0.104 [0–1] | 0.132 [0–1] | 2.042 [0–5] |
| legitimate activated within horizon (rate) | 0.932 [0.88–0.97] | 0.932 [0.88–0.98] | 0.654 [0.57–0.74] | 0.931 [0.88–0.97] |
| legitimate wrongly flagged (campaigns) | 1.994 [0–5] | 2.032 [0–5] | 1.638 [0–4] | 2.02 [0–5] |
| still pending at horizon (campaigns) | 15.336 [10–21] | 15.324 [9–21] | 46.834 [38–56] | 15.614 [10–21] |
| successful independent confirmations (count) | 353.728 [345–362] | 353.602 [343–363] | 314.368 [300–329] | 364.55 [353–375] |
| unsuccessful attempts (count) | 139.74 [116–164] | 138.69 [114–164] | 354.634 [311–393] | 142.978 [118–169] |
| campaigns with false institution contact | 10.682 [6–17] | 10.638 [5–17] | 13.416 [8–20] | 15.124 [9–21] |
| campaign-supplied contacts used by verifiers | 1.128 [0–3] | 0 [0–0] | 1.324 [0–4] | 3.142 [0–7] |
| ... caught by upload contact matching | 0.776 [0–3] | 0 [0–0] | 0.932 [0–3] | 1.218 [0–4] |
| ... accepted towards activation | 0.124 [0–1] | 0 [0–0] | 0.198 [0–1] | 1.14 [0–3] |
| median hours to activation (legitimate) | 41.535 [34.25–51.52] | 41.268 [33.69–51.7] | 60.295 [51.08–71.27] | 41.875 [33.44–51.62] |
| mean hours to activation (legitimate) | 54.309 [46.31–62.9] | 54.089 [45.36–62.28] | 72.353 [60.56–84.69] | 54.355 [46.02–62.59] |
| verification attempts per campaign | 3.685 [3.5143–3.85] | 3.674 [3.5071–3.85] | 4.933 [4.6786–5.1786] | 3.781 [3.6–3.9571] |
| verifier minutes per campaign | 25.227 [23.7643–26.8714] | 25.124 [23.7857–26.6786] | 33.923 [31.7786–36.0857] | 26.204 [24.6–27.8571] |

## Population: prior_150

Campaigns entering confirmation: 81 ({'legitimate': 45, 'fraudulent': 36}). Replications per scenario: 500.

| Metric | reference | careful_verifiers | low_responsiveness | adversarial |
|---|---:|---:|---:|---:|
| fraud prevented from activation (rate) | 0.992 [0.9444–1] | 0.994 [0.9722–1] | 0.994 [0.9722–1] | 0.904 [0.8056–0.9722] |
| fraud activated (campaigns) | 0.304 [0–2] | 0.212 [0–1] | 0.218 [0–1] | 3.45 [1–7] |
| legitimate activated within horizon (rate) | 0.93 [0.8444–0.9778] | 0.932 [0.8667–0.9778] | 0.651 [0.5111–0.8] | 0.933 [0.8667–1] |
| legitimate wrongly flagged (campaigns) | 0.946 [0–3] | 0.9 [0–3] | 0.72 [0–2] | 0.86 [0–3] |
| still pending at horizon (campaigns) | 2.34 [0–6] | 2.264 [0–5] | 16.296 [10–23] | 2.552 [0–5] |
| successful independent confirmations (count) | 153.886 [145–164] | 153.91 [144–164] | 136.162 [125–147] | 173.52 [163–184] |
| unsuccessful attempts (count) | 64.34 [49–84] | 64.232 [48–82] | 173.386 [145–207] | 69.5 [53–89] |
| campaigns with false institution contact | 10.472 [5–16] | 10.538 [5–17] | 15.256 [10–21] | 18.776 [13–25] |
| campaign-supplied contacts used by verifiers | 1.12 [0–3] | 0 [0–0] | 1.516 [0–4] | 3.644 [1–8] |
| ... caught by upload contact matching | 0.81 [0–3] | 0 [0–0] | 1.05 [0–3] | 1.47 [0–4] |
| ... accepted towards activation | 0.25 [0–2] | 0 [0–0] | 0.4 [0–2] | 1.952 [0–5] |
| median hours to activation (legitimate) | 41.751 [31.47–55.92] | 42.002 [30.78–56.6] | 60.825 [43.82–78.46] | 42.054 [31.11–57.59] |
| mean hours to activation (legitimate) | 54.31 [42.25–67.34] | 54.382 [42.33–68.58] | 72.344 [55.93–91.32] | 54.204 [41.79–69.18] |
| verification attempts per campaign | 3.156 [2.9506–3.3827] | 3.145 [2.9259–3.3951] | 4.272 [3.9259–4.6296] | 3.448 [3.1975–3.716] |
| verifier minutes per campaign | 20.113 [18.4815–22.1852] | 20.017 [17.8889–22.037] | 27.935 [25–30.9259] | 23.045 [20.7407–25.3704] |

## Assumptions per scenario

**reference**: `{"p_unreachable": 0.25, "p_legit_record_mismatch": 0.02, "p_fraud_kyc_pass": 0.7, "p_fraud_payee_lookalike": 0.2, "p_spoofed_directory": 0.02, "p_insider_collusion": 0.02, "p_fraud_fake_contact": 0.8, "p_fake_contact_printed": 0.7, "p_legit_wrong_contact": 0.05, "p_careless_verifier": 0.1, "p_borderline_inconclusive": 0.5, "median_response_hours": {"BENEFICIARY": 2.0, "PAYMENT_DESTINATION": 4.0, "INSTITUTION": 24.0}, "minutes_per_attempt": {"BENEFICIARY": 3.0, "PAYMENT_DESTINATION": 3.0, "INSTITUTION": 15.0}, "retry_after_hours": 24.0, "max_attempts_per_check": 3, "horizon_days": 14.0}`

**careful_verifiers**: `{"p_unreachable": 0.25, "p_legit_record_mismatch": 0.02, "p_fraud_kyc_pass": 0.7, "p_fraud_payee_lookalike": 0.2, "p_spoofed_directory": 0.02, "p_insider_collusion": 0.02, "p_fraud_fake_contact": 0.8, "p_fake_contact_printed": 0.7, "p_legit_wrong_contact": 0.05, "p_careless_verifier": 0.0, "p_borderline_inconclusive": 0.5, "median_response_hours": {"BENEFICIARY": 2.0, "PAYMENT_DESTINATION": 4.0, "INSTITUTION": 24.0}, "minutes_per_attempt": {"BENEFICIARY": 3.0, "PAYMENT_DESTINATION": 3.0, "INSTITUTION": 15.0}, "retry_after_hours": 24.0, "max_attempts_per_check": 3, "horizon_days": 14.0}`

**low_responsiveness**: `{"p_unreachable": 0.5, "p_legit_record_mismatch": 0.02, "p_fraud_kyc_pass": 0.7, "p_fraud_payee_lookalike": 0.2, "p_spoofed_directory": 0.02, "p_insider_collusion": 0.02, "p_fraud_fake_contact": 0.8, "p_fake_contact_printed": 0.7, "p_legit_wrong_contact": 0.05, "p_careless_verifier": 0.1, "p_borderline_inconclusive": 0.5, "median_response_hours": {"BENEFICIARY": 2.0, "PAYMENT_DESTINATION": 4.0, "INSTITUTION": 24.0}, "minutes_per_attempt": {"BENEFICIARY": 3.0, "PAYMENT_DESTINATION": 3.0, "INSTITUTION": 15.0}, "retry_after_hours": 24.0, "max_attempts_per_check": 3, "horizon_days": 14.0}`

**adversarial**: `{"p_unreachable": 0.25, "p_legit_record_mismatch": 0.02, "p_fraud_kyc_pass": 0.9, "p_fraud_payee_lookalike": 0.5, "p_spoofed_directory": 0.1, "p_insider_collusion": 0.05, "p_fraud_fake_contact": 0.8, "p_fake_contact_printed": 0.4, "p_legit_wrong_contact": 0.05, "p_careless_verifier": 0.2, "p_borderline_inconclusive": 0.5, "median_response_hours": {"BENEFICIARY": 2.0, "PAYMENT_DESTINATION": 4.0, "INSTITUTION": 24.0}, "minutes_per_attempt": {"BENEFICIARY": 3.0, "PAYMENT_DESTINATION": 3.0, "INSTITUTION": 15.0}, "retry_after_hours": 24.0, "max_attempts_per_check": 3, "horizon_days": 14.0}`

## What the simulation shows about the workflow logic

* Campaign-supplied contacts never count towards activation, including when a careless verifier mislabels a number printed in the uploads (caught by upload contact matching).
* A campaign-supplied number sent *out of band* (not in the uploads) and mislabelled by a careless verifier is indistinguishable from an independent contact; in that case a confederate can confirm. This is the residual human-process risk the policy cannot close by itself.
* With honest independent channels, fraud reaches VERIFIED_ACTIVE only when the independent channel itself is compromised (spoofed directory entry or insider collusion) *and* KYC and payee checks pass.
