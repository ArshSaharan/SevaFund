# Gemini integration pilot — 2026-11-16

**Purpose:** verify the API integration before any full evaluation (not a performance measurement).
**Sample:** 3 synthetic cases from `final_test_scenarios_v3.jsonl` (one legitimate, fraudulent, borderline;
one per category): V3T-071, V3T-131, V3T-201. **Budget:** 9 requests (6 generation, 3 embedding), all used.
**Model:** `gemini-3.8-flash` (configured default); embeddings `gemini-embedding-001`. Each counted call = one
HTTP request (no hidden retries); 6 s pacing.

| Stage | Result |
|---|---|
| Embedding retrieval | 3/3 succeeded (0.6–1.8 s); 100% document coverage |
| Generation, `gemini_no_rag` | 1/3 succeeded — in 174.8 s; 2 × READ_TIMEOUT (180 s) |
| Generation, `gemini_rag` | 0/3 — 2 × HTTP 503, 1 × READ_TIMEOUT |
| `hybrid` | 0/3 (waits for `gemini_rag`) |
| Offline configurations | 6/6 |

**What worked:** authentication, model availability, request formats, the structured-output schema (the one
success validated), caching, failure logging (`failures.jsonl`, sanitized), budget enforcement.

**What did not:** generation latency/availability on `gemini-3.8-flash` — 17% success, the only success took
~175 s. This matches the 2026-11-15 probe (`runs/gemini_model_timeout_comparison_20261115T140856Z`), where
`gemini-3.8-flash` timed out at 180 s while `gemini-3.6-flash` returned a valid response in 1.8 s.

**Not ready for the full evaluation.** Next step (needs the owner's decision): repeat this 9-request pilot with
`GEMINI_MODEL=gemini-3.6-flash` set for the evaluation process only, under a new `--experiment` name (cache keys
include the model, so results never mix). Proceed to the full run only if generation success is ≥ 95% and
p95 latency is well under the timeout.
