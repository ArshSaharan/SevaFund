# Controlled model comparison — gemini-3.6-flash on the frozen pilot (2026-11-16)

**Control:** identical 3 synthetic cases (V3T-071, V3T-131, V3T-201), identical code — git `00654b6`, clean tree;
26 files (framework, production prompt path, RAG, Gemini client, config, schemas, fraud rules, frozen V3, approval
workflow, dataset) hash-identical before and after (`pre_run_freeze.json`). Only `GEMINI_MODEL` differed, set for
the evaluation process alone; the application's configured default (`gemini-3.8-flash`) was not changed.
Budget 9 requests (6 generation, 3 embedding), all used; one HTTP request per counted call; 6 s pacing.

Full comparison: `runs/gemini_model_comparison_20261116T133718Z/report.md`.

| | gemini-3.8-flash | gemini-3.6-flash |
|---|---:|---:|
| Generation succeeded | 1 / 6 | 6 / 6 |
| Timeouts / 503 errors | 3 / 2 | 0 / 0 |
| Success latency mean / p95 (s) | 174.8 / 174.8 | 21.9 / 30.0 |

Retrieval: identical rankings and relevance scores in both runs (embeddings reproducible); 100% document
coverage, but every case has only 1–2 documents, so ranking quality is untested.

Three cases are an integration and reliability check, not an accuracy measurement. 6/6 successes give a
Wilson 95% lower bound of about 61% on the true success rate, so the ≥95% go criterion is not yet established.
