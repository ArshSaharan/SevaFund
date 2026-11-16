# External-confirmation pilot protocol

Under the `ELIGIBLE_PENDING_EXTERNAL_VERIFICATION` policy, the safety of approvals now rests on
human confirmation of three things: the beneficiary, the payment destination and the institution.
The simulation (`evaluation/simulate_external_confirmation.py`) tests the workflow's *logic* under
assumed behaviour. This pilot replaces those assumptions with measurements.

## Measures

All are computed by `evaluation/analyze_confirmation_log.py` from the filled templates in
`evaluation/confirmation_pilot/`.

| Measure | Definition |
|---|---|
| Successful independent confirmations | CONFIRMED attempts through an independent contact that the workflow accepted, per attempt and per check |
| False institution-contact details | Campaigns whose supplied institution contact differs from the independently found one; how often verifiers used such contacts; how many the workflow caught; how many it accepted (target: 0) |
| Unsuccessful verification attempts | UNREACHABLE and INCONCLUSIVE attempts; campaigns still pending at the 14-day horizon |
| Confirmation time | Hours from the first attempt to VERIFIED_ACTIVE (mean, median, p90), and to FLAG for fraudulent campaigns |
| Administrative workload | Attempts and verifier-minutes per campaign; reviews triggered by contradictions |
| Fraud prevented from activation | Fraudulent (red-team) campaigns that never reached VERIFIED_ACTIVE |
| Legitimate impact | Activation rate within 14 days; genuine campaigns wrongly flagged by record mismatches |

## Phase A: process rehearsal

**No real institutions or money; about 1 week.**

- **Setup:** a coordinator plays the hospitals, schools, registries and banks from sealed answer
  sheets (the "external environment" of `independent_test_protocol_v4.md` §3). Some sheets include
  confederates behind campaign-printed or out-of-band numbers.
- **Verifiers:** at least 3 people, given only the workflow rules, with no knowledge of which
  campaigns are fraudulent.
- **Sample:** at least 30 campaigns, about a third of them fraudulent.
- **What it measures:** verifier behaviour, in particular whether campaign-supplied contacts get
  used; the speed of logging; and whether the rules are understood.
- **What it cannot measure:** how real institutions respond.

## Phase B: real institution responsiveness

**Genuine requests only; about 2–3 weeks.**

- **Partners:** about 10 hospitals, 10 educational institutions and the relevant society or trust
  registries, each of which agrees to take part.
- **Sample:** at least 50 confirmations across at least 20 institutions, for **genuine** campaigns
  whose beneficiaries consented, or for agreed test enquiries.
- **What it measures:** reachability, response time, successful confirmations, and the rate of
  genuine-record mismatches (which produce wrong flags).
- **Contacts:** independent contacts only, taken from official directories or registries. Never
  contact anyone in a way that discloses a beneficiary's information without consent.

## Phase C: red-team prevention test

**With institutional consent; about 2 weeks.**

- **Setup:** at least 20 seeded fabricated campaigns that name **consenting** partner institutions.
  The institutions are briefed in advance and know which enquiries are tests. The team controls the
  confederate numbers. Campaigns are never public and never take real donations.
- **What it measures:** fraud prevented from activation; how false contact details are handled; and
  verifier error under realistic pressure.
- **Ethics:** do not deceive anyone who has not agreed. A spoofed-directory or insider-collusion
  scenario may only be simulated with the institution's explicit participation.

## Go / no-go thresholds

The project owner sets these **before** the pilot starts; the values below are suggestions.

- Campaign-supplied contacts accepted towards activation: **0**.
- Red-team fraud prevented from activation: **≥ 95%**, with the lower bound of its 95% interval
  reported.
- Median time to activation for genuine campaigns: **≤ 72 hours**; genuine campaigns wrongly flagged:
  **≤ 3%**.
- Verifier time: **≤ 30 minutes** per campaign on average.

## Data handling

- Filled logs contain real contact details. Keep them outside this repository, on the operator's
  secured storage.
- Only aggregate `metrics.json` outputs are shared.
- Beneficiary data is processed only with consent and under the platform's data-protection policy.
- Delete raw logs at the end of the retention period.
