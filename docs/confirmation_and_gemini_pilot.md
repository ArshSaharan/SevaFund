# External confirmation, Gemini pilot and independent-test preparation

Development only. All work is on branch `dev/verifier-v2-v3-evaluation`. Nothing has been deployed,
merged or pushed.

## 1. Work preserved on a branch

Branch `dev/verifier-v2-v3-evaluation` holds:

- `81aec5b`: previously uncommitted changes to the verifier path, which the frozen evaluations'
  hashes depend on;
- `1c7e739`: the development-only verifiers, workflow and evaluation suite;
- a follow-up commit with the work described below.

Before each commit, all candidate files were scanned for API-key patterns, private-key blocks,
assigned secrets, bearer tokens, and the literal values in `.env`.

- `.env`, `*.db` and the SQLite journal files are excluded; `*.sqlite3-shm/-wal` was added to
  `.gitignore`.
- All data are synthetic.

**One finding for the owner.** The `SECRET_KEY` in the local `.env` is the placeholder value already
committed in `.env.example`, which is public on GitHub. Nothing new was leaked, but any non-local
deployment must use a freshly generated secret.

## 2. External-confirmation workflow

The confirmation step is now the system's safety barrier, and it has not been measured. This round
adds three pieces:

| Piece | File | What it gives |
|---|---|---|
| Metrics | `evaluation/confirmation_metrics.py` | Successful independent confirmations; false institution-contact details (encountered, used, caught, accepted); unsuccessful attempts; time to activation and to flag; workload in attempts and verifier-minutes; fraud prevented from activation; legitimate impact |
| Real-pilot scoring | `evaluation/analyze_confirmation_log.py`, `evaluation/confirmation_pilot/` | Replays a verifier log through the real workflow code, so a pilot is scored with exactly the enforced rules |
| Pilot protocol | `evaluation/confirmation_pilot_protocol.md` | Phase A: rehearsal with role-played institutions. Phase B: real institution responsiveness, with consent. Phase C: a red-team prevention test with consenting institutions. Go/no-go thresholds are set by the owner beforehand. |
| Simulation | `evaluation/simulate_external_confirmation.py` | Monte Carlo that drives the real workflow under **assumed** contact behaviour |

### Simulation results

**Run:** `evaluation/runs/confirmation_simulation_20261116T132338Z/`. These are assumptions, not
measurements: 500 replications per scenario, applied to the 140 campaigns V3 sends to
pending-confirmation on the 300-case final test.

| Under the stated assumptions | Reference | Careful verifiers | Low responsiveness | Adversarial |
|---|---:|---:|---:|---:|
| Fraud prevented from activation | 99.2% | 99.5% | 99.3% | 89.8% |
| Fraudulent campaigns activated (of 20) | 0.17 | 0.10 | 0.13 | 2.04 |
| Legitimate activated within 14 days | 93.2% | 93.2% | 65.4% | 93.1% |
| Legitimate wrongly flagged (of 100) | 2.0 | 2.0 | 1.6 | 2.0 |
| Campaign-supplied contacts accepted | 0.12 | 0 | 0.20 | 1.14 |
| Median hours to activation (legitimate) | 41.5 | 41.3 | 60.3 | 41.9 |
| Verifier minutes per campaign | 25.2 | 25.1 | 33.9 | 26.2 |

**What the simulation establishes about the workflow's logic.** These conclusions are independent of
the parameter values:

- **Contacts printed in the uploads never count**, even when a verifier mislabels them as directory
  numbers; they are caught by contact matching.
- **The residual human-process risk:** a contact the fraudster sends *outside* the uploads, which a
  careless verifier then mislabels, cannot be told apart from an independent contact. That is the
  only route for the "accepted" numbers above, and it is zero when verifiers are careful.
- **With honest independent channels, fraud activates only when the channel itself is compromised**
  (a spoofed directory entry or insider collusion) *and* KYC and payee checks also pass.

**What it cannot establish:** the real rates of unreachable institutions, record mismatches,
spoofing, collusion or careless verification. Those decide the numbers above, and only the pilot can
measure them.

## 3. Gemini pilot

### Correction to the quota estimate

The full plan makes 180 HTTP requests: 120 generation and 60 embedding.

- The earlier "6 days" assumed embeddings have their own per-model quota.
- If every request shares a 20-per-day limit, it is **9 days**.
- Neither figure includes failed requests, which also consume quota.

Two framework fixes went in with this correction:

- **Accurate request counting.** The shared client used to retry 429 and 5xx responses internally,
  so a counted call could become two requests. Every counted call is now exactly one HTTP request;
  retries happen on resumed runs instead.
- **Rate limiting.** Requests are paced (6 s by default), and rate-limit errors stop the run.

### Pilot result

**Files:** `evaluation/runs/gemini_pilot_v3/`, including `PILOT_NOTES.md`. The pilot ran 3 synthetic
cases (one per label and category) with a budget of 9 requests, all of which were used.

| Stage | Result |
|---|---|
| Embedding retrieval | 3/3 succeeded (0.6–1.8 s); 100% document coverage |
| Generation, Gemini without RAG | 1/3; the success took **174.8 s**; 2 read timeouts at 180 s |
| Generation, Gemini with RAG | 0/3: two HTTP 503 responses and one read timeout |
| Offline configurations | 6/6 |

- **Integration verified:** authentication, the model name, request formats, structured-output
  validation, caching, failure logging and budget enforcement all work.
- **Not ready:** generation on `gemini-3.8-flash` is unreliable (17% success, about 175 s
  latency). That matches the 15 November probe, where 3.8-flash timed out while
  `gemini-3.6-flash` answered in 1.8 s.
- **Next step, for the owner to decide:** repeat the 9-request pilot with
  `GEMINI_MODEL=gemini-3.6-flash` set for the evaluation process only, under a new experiment name.
  Proceed to the full run only if generation succeeds at least 95% of the time and p95 latency is
  well under the timeout.

## 4. Independent-test preparation

| File | Purpose |
|---|---|
| `evaluation/independent_test_v4/AUTHORING_GUIDE.md` | Instructions for outside authors. It reveals none of the verifier's rules and covers the five fraud patterns, gold evidence and the external-contact environment. |
| `evaluation/independent_test_v4/example_case.json` | A complete example case (consistent fabrication with a confederate contact) |
| `evaluation/independent_test_v4/labeling_sheet_template.csv` | Blind labelling sheet |
| `evaluation/validate_independent_submission.py` | Checks schema, ≤3 cases per group, quotas (30/30/15 groups per category), ≥15% of fraud groups per pattern, keyword-free cases, and near-duplicates against all seven previously used corpora. Seals valid submissions, and computes Cohen's κ for two labelling sheets. |

These implement `evaluation/independent_test_protocol_v4.md`.

**What remains is people:** independent authors and labellers, about 225 groups, and a coordinator
who never sees the verifier code.

## 5. Tests added this round

- `tests/test_confirmation_simulation.py` (10): safety invariants, metric definitions, real-log
  replay, and the templates.
- `tests/test_gemini_evaluation_framework.py` (now 18): one HTTP request per counted call,
  rate-limit stop, both quota scenarios, and the balanced pilot.
- `tests/test_independent_submission_validator.py` (10).
