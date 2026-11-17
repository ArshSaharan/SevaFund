# SevaFund fraud-verification prototype: local demonstration

You do not need an API key, network access or any paid service. Gemini answers are scripted and external confirmations
are simulated, so this demonstrates the workflow logic, not real-world verification. Full details are in
`docs/SEVAFUND_FINAL_REPORT.md`.

## Setup (once)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=""          # makes sure nothing can call the API
```

## 1. Walk through the prototype (about a second)

```bash
python evaluation/final_evaluation/demo.py
```

It shows four scenarios, each with:
- the automated decision and its explanation;
- what frozen V3, hybrid v2 and hybrid v3 decided on the same input;
- the simulated independent confirmations (beneficiary, institution, payment destination, amount);
- the final state, the disbursement limit and the audit-chain check.

| Scenario | What to look for |
|---|---|
| `FE-LC-MED-03` | A genuine campaign raising only the balance after insurance activates. The insurer's share is deducted in the amount check |
| `FE-FS-MED-02` | A consistent but inflated estimate passes every automated check. The hospital billing desk's figure stops it at the AMOUNT check, where earlier versions activated it |
| `FE-LI-MED-01` | A genuine patient at a government hospital with no formal quotation gets an information request, then the assisted route, and activates only after all four independent confirmations |
| `FE-FD-EDU-05` | Substituted bank details are flagged with both quotes as evidence |

Any other scenario can be shown by its ID, for example the collusive fraud case that still activates:

```bash
python evaluation/final_evaluation/demo.py FE-FS-COM-03
```

All 60 IDs are in `evaluation/final_evaluation/scenarios.jsonl`.

## 2. Re-run the final evaluation (about a second)

```bash
python evaluation/final_evaluation/run_final_evaluation.py
```

This writes `evaluation/final_evaluation/results/`:
- `metrics.json`: counts, percentages and Wilson intervals for all four systems;
- `case_level.csv` and `case_level.jsonl`.

The output is identical on every run.

## 3. Run the tests and integrity checks

```bash
python -m pytest -q tests/test_hybrid_v4.py          # 34 hybrid v4 tests
python -m pytest -q tests/test_dev_hybrid_v4_integration.py   # 17 end-to-end tests of hybrid v4 inside the app
python -m pytest -q tests/test_auth_hardening.py tests/test_access_control.py   # 43 authentication and access-control tests
python -m pytest -q                                   # full suite on integration/hybrid-v4-auth: 576 pass, 0 fail
python evaluation/freeze_hybrid_v3.py verify          # frozen V3, hybrid v2 and hybrid v3 unchanged
python evaluation/check_frozen_benchmark_reproducibility.py
```

## 4. Use hybrid v4 from Python

```python
from datetime import date
from app.services.development_hybrid_v4 import assess_case, start, record_confirmation, Confirmation, Check, activation_status
from app.services.development_approval_workflow.schemas import ConfirmationOutcome, ContactSource

decision = assess_case(case_dict, gemini_outcome_dict_or_None, evidence_chunks, date.today())
print(decision.explanation)
record = start(decision.decision, case_dict, decision.information_requests, decision.manual_route, decision.audit_payload())
record_confirmation(record, Confirmation(check=Check.AMOUNT, outcome=ConfirmationOutcome.CONFIRMED,
                                         contact_source=ContactSource.OFFICIAL_DIRECTORY, verifier_id="v1",
                                         stated_amount_inr=185000))
print(activation_status(record))
```

## 5. Hybrid v4 inside the application (development feature flag)

**Authentication (integration branch `integration/hybrid-v4-auth`).**
- **Signing key:** the app refuses to start without a strong `SECRET_KEY` in `.env`.
- **Logging in:** creating campaigns and uploading documents require a login; there is no anonymous demo user. Use the seeded accounts (`python seed_data.py`), or register and log in.
- **Administrators:** only an authenticated administrator can promote another user (`POST /api/auth/promote-admin`).
- **Google and OTP sign-in:** Google sign-in accepts only verified Google ID tokens; OTP codes go only by SMS.

**The flag is OFF by default.** With it off, the application behaves exactly as before. That includes the production
behaviour of publishing a campaign as ACTIVE when `POST /api/campaigns/{id}/verify` returns AUTO_APPROVE (a score of
at least 80).

**Settings.** All are environment variables read on each request; none is in `app/config.py`.

| Variable | Values | Meaning |
|---|---|---|
| `SEVAFUND_DEV_HYBRID_V4` | `1` (also `true`, `yes`, `on`); unset = off | Turns the integration on |
| `SEVAFUND_DEV_HYBRID_V4_GEMINI` | `off` (default), `mock-approve`, `mock-nmi`, `mock-flag-unquoted`, `mock-fail` | Offline scripted Gemini stand-in. There is no live mode; the integration never calls the Gemini API. With `off`, hybrid v4 never approves anything |
| `GEMINI_API_KEY` | set to an empty value | Keeps the production verifier, which still computes the informational score, on its offline heuristics |

**What changes when the flag is on:**
- **Creating or re-verifying a campaign** runs hybrid v4 on its text and uploaded `.txt`, `.md` or `.pdf` documents. The
  campaign status follows the hybrid v4 workflow, never the score:

  | Hybrid v4 workflow state | Campaign status |
  |---|---|
  | provisional approval, information request, verification error | `PENDING_VERIFICATION` |
  | review | `FLAGGED` |
  | rejected | `REJECTED` |
  | all four independent confirmations recorded | `ACTIVE` |

- **ACTIVE needs all four checks:** beneficiary, institution, payment destination and amount, each confirmed through an
  independent source. Recording them requires an admin or trust reviewer who is not the campaign's creator.
- **Admins cannot activate.** An admin APPROVE returns HTTP 409 unless the campaign is FLAGGED; then it clears the
  campaign back to pending, and all four checks start again.
- **Donations and payouts are refused until ACTIVE.** Payouts are capped at the independently confirmed amount.
- **The goal cannot change** once the campaign is pending confirmation, under review or active.
- **Development endpoints** are available (hidden from `/docs`; they return 404 when the flag is off):
  - `GET /api/dev/hybrid-v4/campaigns/{id}`: state, explanation, findings, pending checks, and the audit log for staff;
  - `POST /api/dev/hybrid-v4/campaigns/{id}/confirmations` with a body such as
    `{"check": "AMOUNT", "outcome": "CONFIRMED", "contact_source": "OFFICIAL_DIRECTORY", "stated_amount_inr": 185000, "other_payers_inr": 0}`;
  - `POST /api/dev/hybrid-v4/campaigns/{id}/assisted-cost-review` (body `{}`): for a campaign whose only gap is a
    missing quotation.

### 5a. Quickest demonstration (in-process; temporary database and uploads)

```bash
python evaluation/final_evaluation/demo_app_integration.py
```

This takes about 3 seconds. It runs the real app with the flag on, against a temporary database and upload folder;
your `crowdfund.db` and `uploads/` are not touched. It shows three cases:
1. **Production score 83.8, still pending.** The admin APPROVE returns 409, donations are refused, the campaign stays
   pending after three confirmations, and it becomes ACTIVE only after the fourth (amount).
2. **Inflated goal.** The billing desk's figure sends it to FLAGGED.
3. **No formal quotation.** An information request, then the assisted route, then four confirmations, then ACTIVE.

### 5b. Running the real server with the flag

The server stores uploaded documents in `uploads/` (production behaviour). Delete the folder afterwards if you do not
want to keep the demo files.

**Terminal 1** (use a separate database: `seed_data.py` drops every table in the configured one):

```bash
source .venv/bin/activate
export SEVAFUND_DEV_HYBRID_V4=1 SEVAFUND_DEV_HYBRID_V4_GEMINI=mock-approve GEMINI_API_KEY=""
export DATABASE_URL=sqlite:///./dev_hybrid_v4.db
python seed_data.py && python run.py
```

**Terminal 2** (bash or zsh; needs `curl` and `python3`):

```bash
API=http://localhost:8000/api
login() { curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"$1\",\"password\":\"$2\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'; }
CREATOR=$(login priya.sharma@example.com password123); ADMIN=$(login admin@crowdfund-trust.in admin123)

# Two supporting documents dated relative to today
python3 - <<'EOF'
import datetime as dt
f = lambda n: (dt.date.today() + dt.timedelta(days=n)).strftime("%d/%m/%Y")
open("estimate.txt", "w").write(f"Sushruta Hospital, Wardha Road, Nagpur 440015. Estimate No. SH/EST/26/4471 Date: {f(-3)}\n"
  "Patient: Kamala Bai, 68 F, UHID SH-208813\nProcedure: Left hip hemiarthroplasty\nImplant Rs 75,000; Surgery and OT "
  f"Rs 55,000; Ward 4 days Rs 32,000; Medicines Rs 23,000\nTotal estimate Rs 1,85,000. Planned surgery date: {f(7)}. "
  "Billing Executive (signed)")
open("note.txt", "w").write(f"Sushruta Hospital casualty {f(-4)}. Kamala Bai 68 F. Displaced fracture neck of left femur "
  "after a fall at home. Advised hemiarthroplasty. Dr P. Wankhede MS Ortho")
EOF

up() { curl -s -X POST $API/documents/upload -H "Authorization: Bearer $CREATOR" \
  -F "file=@$1;type=text/plain" -F "title=$2" -F "doc_type=$3"; }
D1=$(up estimate.txt "Hospital estimate" HOSPITAL_ESTIMATE); D2=$(up note.txt "Orthopaedic note" CLINICAL_NOTE)
CID=$(curl -s -X POST $API/campaigns -H "Authorization: Bearer $CREATOR" -H 'Content-Type: application/json' \
  -d "{\"title\":\"Hip surgery for Kamala Bai\",\"category\":\"MEDICAL\",\"goal_amount\":185000,
       \"story\":\"Kamala Bai, 68, fractured her left hip. Sushruta Hospital will operate next week.\",
       \"beneficiary_name\":\"Kamala Bai\",\"city\":\"Nagpur\",\"state\":\"Maharashtra\",\"proof_documents\":[$D1,$D2]}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# Hybrid v4's decision, explanation and pending checks
curl -s $API/dev/hybrid-v4/campaigns/$CID -H "Authorization: Bearer $ADMIN" | python3 -c \
  'import sys,json;r=json.load(sys.stdin);print(r["campaign_status"],r["workflow_state"]);print(r["explanation"])'

# An admin cannot activate it (HTTP 409); a donation is refused (HTTP 400)
curl -s -o /dev/null -w "admin approve: %{http_code}\n" -X POST $API/admin/campaigns/$CID/decision \
  -H "Authorization: Bearer $ADMIN" -H 'Content-Type: application/json' -d '{"decision":"APPROVE"}'
curl -s -o /dev/null -w "donation: %{http_code}\n" -X POST $API/campaigns/$CID/donate \
  -H 'Content-Type: application/json' -d '{"amount":2500}'

# Record the simulated independent confirmations one by one
conf() { curl -s -X POST $API/dev/hybrid-v4/campaigns/$CID/confirmations -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' -d "$1" | python3 -c \
  'import sys,json;r=json.load(sys.stdin);print(r["campaign_status"],"pending:",r["activation"]["pending_checks"])'; }
conf '{"check":"BENEFICIARY","outcome":"CONFIRMED","contact_source":"PLATFORM_KYC"}'
conf '{"check":"INSTITUTION","outcome":"CONFIRMED","contact_source":"OFFICIAL_DIRECTORY"}'
conf '{"check":"PAYMENT_DESTINATION","outcome":"CONFIRMED","contact_source":"PLATFORM_KYC"}'
curl -s -o /dev/null -w "donation: %{http_code}\n" -X POST $API/campaigns/$CID/donate \
  -H 'Content-Type: application/json' -d '{"amount":2500}'
conf '{"check":"AMOUNT","outcome":"CONFIRMED","contact_source":"OFFICIAL_DIRECTORY","stated_amount_inr":185000}'
curl -s -o /dev/null -w "donation: %{http_code}\n" -X POST $API/campaigns/$CID/donate \
  -H 'Content-Type: application/json' -d '{"amount":2500}'
```

**Expected output:**
- `PENDING_VERIFICATION ELIGIBLE_PENDING_CONFIRMATION`, followed by the explanation;
- `admin approve: 409`, then `donation: 400`;
- three lines showing the campaign still `PENDING_VERIFICATION` with fewer checks pending each time;
- `donation: 400`;
- `ACTIVE pending: []`;
- `donation: 201`.

**To see the other paths:**
- **Inflated goal:** record `"stated_amount_inr": 120000` for AMOUNT; the campaign becomes FLAGGED.
- **Pending checks:** use `UNREACHABLE` or `INCONCLUSIVE`, or a `CAMPAIGN_SUPPLIED` source; the campaign stays pending.
- **No formal quotation:** restart the server with `SEVAFUND_DEV_HYBRID_V4_GEMINI=mock-nmi`, then use the
  assisted-cost-review endpoint.

**To return to production behaviour:** `unset SEVAFUND_DEV_HYBRID_V4` and restart. Campaigns created under the flag keep
their status, and their hybrid v4 records stay in the `dev_hybrid_v4_records` table.

**The Angular frontend** (`npm start` in `frontend/`) works unchanged. It shows the campaign status, but it has no
screens for the development endpoints.
