# Gemini model comparison on the frozen pilot

Same 3 synthetic cases (V3T-071, V3T-131, V3T-201), same frozen code (git `00654b6`, 26 files hash-identical before and after: **True**), same production prompt, budget 9 requests per model, 6 s pacing, one HTTP request per counted call. Only the generation model differs. A 3-case pilot measures integration and reliability, **not accuracy**.

## Reliability, latency and API usage

| | gemini-3.8-flash | gemini-3.6-flash |
|---|---:|---:|
| Requests consumed (generation / embedding) | 6 / 3 | 6 / 3 |
| Gemini without RAG: succeeded / attempted | 1 / 3 | 3 / 3 |
| Gemini with RAG: succeeded / attempted | 0 / 3 | 3 / 3 |
| Timeouts (180 s) | 3 | 0 |
| Other failures | {"SERVER_ERROR": 2} | {} |
| Success latency, mean (s) | 174.81 | 21.94 |
| Success latency, p95 nearest-rank (s) | 174.81 | 30.03 |
| Successful latencies (s) | 174.81 | 8.58, 18.76, 19.04, 25.35, 29.89, 30.03 |
| Seconds spent on failed requests | 565.2 | 0 |
| Embedding requests succeeded | 3 / 3 | 3 / 3 |

With n ≤ 6 successes, the nearest-rank p95 equals the slowest observed response.

## Evidence retrieval

| Case | Docs | Embedding ranking (run A) | Same in run B | Max relevance Δ | Coverage | Lexical retrieves same docs |
|---|---:|---|---|---:|---:|---|
| V3T-071 | 1 | Committee review copy | True | 0.0 | 1.0 | True |
| V3T-131 | 1 | Course registrar calendar | True | 0.0 | 1.0 | True |
| V3T-201 | 2 | Supplier's itemized project quotation, Cooperative works authorization | True | 0.0 | 1.0 | True |

Each pilot case has 1–2 short documents, so every retriever returns all of them; this checks that retrieval works and is reproducible, not that it ranks well. Ranking quality needs the v4 test set's gold evidence annotations.

## Verification decisions

| Case | label | heuristics_only | heuristics_lexical | gemini_no_rag@gemini-3.8-flash | gemini_rag@gemini-3.8-flash | hybrid@gemini-3.8-flash | gemini_no_rag@gemini-3.6-flash | gemini_rag@gemini-3.6-flash | hybrid@gemini-3.6-flash | v3_decision |
|---|---|---|---|---|---|---|---|---|---|---|
| V3T-071 | borderline | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | — | — | — | NEEDS_MORE_INFORMATION | NEEDS_MORE_INFORMATION | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| V3T-131 | fraudulent | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | — | — | — | NEEDS_MORE_INFORMATION | REJECTED | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION |
| V3T-201 | legitimate | FLAG_FOR_REVIEW | FLAG_FOR_REVIEW | NEEDS_MORE_INFORMATION | — | — | NEEDS_MORE_INFORMATION | APPROVED | APPROVED | APPROVED |

## Disagreements between Gemini and the deterministic fallback

Pairs: `gemini_no_rag` vs `heuristics_only` (no documents); `gemini_rag` vs `heuristics_lexical` (the production fallback when documents are present). A disagreement is a different decision or a different fraud flag (FLAG/REJECT or any red flag).

| Model | Case | Label | Gemini config → decision (flagged, red flags) | Fallback → decision (flagged) |
|---|---|---|---|---|
| gemini-3.8-flash | V3T-201 | legitimate | gemini_no_rag → NEEDS_MORE_INFORMATION (True, 2) | heuristics_only → FLAG_FOR_REVIEW (True) |
| gemini-3.6-flash | V3T-071 | borderline | gemini_no_rag → NEEDS_MORE_INFORMATION (True, 3) | heuristics_only → FLAG_FOR_REVIEW (True) |
| gemini-3.6-flash | V3T-131 | fraudulent | gemini_no_rag → NEEDS_MORE_INFORMATION (True, 2) | heuristics_only → FLAG_FOR_REVIEW (True) |
| gemini-3.6-flash | V3T-201 | legitimate | gemini_no_rag → NEEDS_MORE_INFORMATION (True, 2) | heuristics_only → FLAG_FOR_REVIEW (True) |
| gemini-3.6-flash | V3T-071 | borderline | gemini_rag → NEEDS_MORE_INFORMATION (True, 2) | heuristics_lexical → FLAG_FOR_REVIEW (True) |
| gemini-3.6-flash | V3T-131 | fraudulent | gemini_rag → REJECTED (True, 3) | heuristics_lexical → FLAG_FOR_REVIEW (True) |
| gemini-3.6-flash | V3T-201 | legitimate | gemini_rag → APPROVED (False, 0) | heuristics_lexical → FLAG_FOR_REVIEW (True) |

Offline configurations reproduced identically across the two runs: **True**.
