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
python -m pytest -q                                   # full suite: 513 pass; 1 known, unrelated login-test failure
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

## The web application

The FastAPI and Angular application runs as described in the main `README.md` (`python run.py`, then `npm start` in
`frontend/`). It still uses the production verifier: **the hybrid v4 prototype is not wired into the live app.**
