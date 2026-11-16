# SevaFund V3 one-time final-test protocol

## Scope

This protocol evaluates the frozen offline V2 and V3 engines on the same 300 new synthetic fundraising scenarios. It is a controlled software evaluation, not a claim of real-world or human-independent validation.

The final corpus is generated only after `development_candidate_v3_freeze.json` is written and verified. Its scenario families are authored separately from V3 development families and all previously used 200-, 100-, 150-, V1-, and V2-development corpora. The generator does not read a verifier, labels, thresholds, or previous datasets.

## Corpus design

- 300 cases: 100 legitimate, 100 fraudulent, 100 borderline.
- 100 cases each in medical, education, and community fundraising.
- 30 scenario families, ten variants per family, with a family and source label on every row.
- Includes high but justified medical costs, incomplete/conditional records, cross-document identity/amount/quantity/time conflicts, suspicious payees, and internally consistent documents whose false provenance is known only to the synthetic author.
- All content and labels are synthetic. One author wrote the scenarios and assigned labels; no independent author or human adjudication was available.
- A consistent fabricated dossier is intentionally not inferable from its text alone. Its label reflects the author's hidden provenance. This tests a known evidence limit rather than implying that the verifier can discover hidden facts.

## Frozen systems and execution

The V3 code and default configuration are hashed in `development_candidate_v3_freeze.json`; the V2 package must still match its existing V2 freeze manifest. A freeze mismatch stops the run. The final runner reserves an output directory keyed by the final dataset hash and refuses to reuse it, preserving the single-run record.

```sh
./.venv/bin/python -B evaluation/verify_candidate_v3_freeze.py
./.venv/bin/python -B evaluation/generate_final_test_v3.py
./.venv/bin/python -B evaluation/evaluate_final_test_v3.py
```

Both engines receive identical campaign text and full document text, with identical case IDs and ground-truth labels. V2 receives only its existing schema fields. V3 receives the same values plus the explicit goal-currency field. No code, thresholds, labels, or dataset rows may be changed after looking at final results. No Gemini, embeddings, paid API, or semantic-RAG calls are made.

## Metrics

Primary precision, recall, F1, and false-positive rate compare the 100 legitimate and 100 fraudulent cases. Borderline cases are not forced into the binary negative class. They appear in a separate three-class disposition matrix (`approved`, `fraud/review`, `unresolved`). `FLAG_FOR_REVIEW` and `REJECTED` count as detection positives; an information request is not a fraud accusation.

The report also gives fraudulent and legitimate auto-approval counts, manual-review and information-request rates, rejection and runtime-error rates, category results, confusion matrices, and mean/p50/p95 latency. Case-level predictions and explanations are saved beside the report. A 0% synthetic error rate does not establish operational reliability.

## Interpretation limits

The corpus is synthetic and authored by the same project agent that built V3. Family-separated development/validation splits reduce literal template leakage but do not provide independent authorship. Internal consistency cannot authenticate a document; the offline engine can identify contradictions in supplied text but cannot establish whether an internally consistent dossier is fabricated. The report must disclose any such fraudulent auto-approvals. Offline lexical/full-text checks are not semantic RAG, and these results do not measure Gemini.
