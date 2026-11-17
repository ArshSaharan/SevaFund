# Fundraising verification evaluation

`fundraising_scenarios.jsonl` is a **fully synthetic** held-out evaluation set of 200 scenarios. Beneficiaries, campaign stories, patient identifiers, documents, and donation requests are invented. Some public hospital names appear as context, but all associated records and claims are fabricated for testing and do not represent those institutions. The generator uses scenarios and combinations different from the existing verifier development tests; it is not a statistically representative sample of real fraud.

| Label | Cases |
|---|---:|
| Legitimate medical | 60 |
| Fraudulent medical | 60 |
| Suspicious or borderline (medical/education/community) | 40 |
| Legitimate education/social | 20 |
| Fraudulent education/social | 20 |
| **Total** | **200** |

Run from the repository root with:

```bash
.venv/bin/python evaluation/evaluate_fundraising.py
```

By default, the evaluator disables Gemini network calls and API billing, and measures the deterministic local heuristic fallback plus its RAG lexical retrieval path. Synthetic evidence text is written to a temporary directory and removed after each run. An operator can explicitly pass `--live-gemini` with `GEMINI_API_KEY` configured to measure the full Gemini generation and embedding path; it preflights both endpoints before processing cases, then makes external requests for every case and may incur charges. The latest live attempt passed preflight, but only a subset of verification calls returned Gemini results; the rest used the local fallback. Always check the success/fallback counts and model attribution in the report before interpreting its aggregate metrics as Gemini performance. It reports precision, recall, F1, false-positive rate (both including borderline cases and for clearly legitimate cases alone), borderline flag rate, and mean/median/p95 latency in `results.json`, with case-level decisions in `predictions.csv`.

For the binary metrics, `fraudulent` is positive; both `legitimate` and `borderline` are negative. This deliberately counts a flagged borderline case as a false positive to reflect the stated priority of avoiding unnecessary blocks. The `flagged` decision mirrors campaign submission: recommendation `FLAG_FOR_REVIEW` or `REJECT`, or any red flag. `NEEDS_MORE_INFO` alone is not counted as flagged.

Treat these results as an implementation sanity check only. A separate, blinded, human-reviewed set of real cases is needed before drawing conclusions about production fraud recall or beneficiary impact. Do not tune rules on this holdout; create a new holdout for later comparisons.

## Follow-up diagnostic run

The rules were later updated for category-aware specificity and broader high-confidence fraud indicators after reviewing errors on this synthetic set. The follow-up at `runs/local_improved_after_category_fix/` is therefore exploratory and is not an independent holdout estimate. The original `results.json`, `predictions.csv`, dataset, and earlier live report remain preserved. Use a newly generated, separately reviewed holdout for future rule or prompt changes.

## Development candidate v2 (November 2026)

A separate development-only verifier (`app/services/development_verifier_v2/`) is evaluated on a
new 120-case corpus (`development_scenarios_v2.jsonl`, family-level tune/validation split) with
`evaluate_development_candidate_v2.py --split all --require-frozen`. Design, results, failure
analysis, limitations and reproduction commands are in `docs/development_verifier_v2.md`; the
independent final-test protocol is `final_test_protocol_v2.md`. None of the corpora above were
modified, and none of these results are real-world or Gemini performance.

## Development candidate V3 (November 2026)

V3 (`app/services/development_verifier_v3/`) was developed on `development_scenarios_v3.jsonl`,
frozen (`development_candidate_v3_freeze.json`), and run once against V2 on the post-freeze synthetic
300-case `final_test_scenarios_v3.jsonl` (`runs/final_test_v3_31f16ae955c4/`). The consolidated
results, the family-level analysis (30 effective units) and the assessment are in
`docs/development_verifier_v3.md`. Do not re-run the final-test generator or evaluator.

## Approval workflow, V3 prior-benchmark diagnostic, Gemini framework (November 2026)

See `docs/approval_workflow_and_v3_diagnostics.md`. The diagnostic run
`runs/diagnostic_v3_prior_benchmarks_ba1b045e8b9d/` was one-time: the 200-, 100- and 150-case sets
are previously used diagnostic data, not independent tests. `gemini_evaluation_framework.py` is
prepared but has not been executed. Future performance claims follow `independent_test_protocol_v4.md`.

## Hybrid v3 evaluation candidate and the v5 protocol draft (November 2026)

Hybrid v3 (`app/services/development_hybrid_v3`, policy `hybrid-v3-dev-1`) is frozen as an evaluation candidate
in `hybrid_v3_freeze.json`; check it with `python evaluation/freeze_hybrid_v3.py verify` (offline). The manifest
records commits, file hashes, the captured prompt and model configuration, a behavioural fingerprint, test results
and known limitations. `independent_test_protocol_v5.md` is a **draft** independent-evaluation protocol for it
(author and labeller kit in `independent_test_v5/`); it is not sealed and has not been executed. All results so far
are development results.
