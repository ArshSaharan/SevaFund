# SevaFund Verification Engine V3 — design

## Intent

Develop a versioned, development-only verifier that improves V2's weak performance on summary-style and unfamiliar evidence while reducing avoidable information requests. Maintain an honest boundary between documentary consistency and issuer authenticity. Preserve the production engine, V1, V2, and every prior corpus and result.

## Chosen approach

**A separate V3 package based on V2's modular architecture.** V2 remains byte-for-byte frozen. V3 gets its own schemas, Decimal currency parser, category evidence policy, consistency checks, decision policy, configuration, test suite, and evaluation runner. The existing production heuristic remains the baseline. A parallel rewrite from scratch would discard tested V2 extraction and audit patterns; changing V2 behind a flag would invalidate its freeze and make paired comparisons ambiguous.

## Goals

- Parse monetary facts as `Decimal` plus ISO currency, with explicit role and source provenance. Recognize INR, USD, GBP, EUR, AUD, CAD, SGD, AED and other explicitly identified currencies; lakh/crore magnitudes; decimals; Western and Indian digit grouping; and written values. Never compare unlike currencies without an explicitly supplied verified conversion. Malformed monetary fields produce a controlled verification error or unresolved fact, never approval.
- Separate critical requirements (beneficiary/payment recipient traceability and the core claimed need) from optional confidence-building material. Optional documents do not by themselves force `NEEDS_MORE_INFORMATION`.
- Record evidence that supports or contradicts a claim, evidence that is absent or unreadable, and issuer authenticity that is unavailable. Cross-document consistency is not issuer authentication.
- Detect identity, destination, amount, currency, date, institution, service, settlement and eligibility conflicts across claims and documents. Preserve category-specific checks for medical, education and community fundraising.
- Keep five outcomes distinct: `APPROVED`, `NEEDS_MORE_INFORMATION`, `FLAG_FOR_REVIEW`, `REJECTED`, `VERIFICATION_ERROR`. Errors cannot approve. Rejection needs multiple independent material findings; uncertainty and missing evidence do not establish fraud.
- Evaluate V2 and V3 on identical new development cases; run ablations for category checks, cross-document checks, money parsing, requirement tiers, and uncertainty/decision handling.
- Freeze V3 before generating the final synthetic test corpus; run the frozen systems once and do not tune on those outcomes.

## Dataset and evaluation design

Create a new deterministic development corpus of 180 synthetic scenarios, split by complete scenario family and document-source group into 120 tune and 60 validation cases. Balance legitimate, fraudulent and borderline labels within each family and represent medical, education and community campaigns in both splits. Do not reuse prior narrative templates or use verifier findings to assign labels. Include fraud detectable from dossier evidence, realistic but internally consistent fabrication that cannot be externally authenticated offline, ambiguous cases, incomplete legitimate proof, unusual supported costs, and cross-document conflicts. The evaluator must not pass labels, split names, scenario-family names, or adjudication notes into either verifier.

After V3 is frozen, generate a distinct 300-case test corpus with 100 cases per category and a preregistered label balance. Because no independent human author/adjudicator is available in this environment, label this corpus as synthetic and single-author; do not describe it as independently authored or human-adjudicated. Freeze the dataset hash before the single paired V2/V3 run. Report this limitation and any cases where fraud is not detectable from the dossier alone.

Primary fraud metrics treat only `FLAG_FOR_REVIEW` and `REJECTED` (plus baseline red flags, mirroring its submission behavior) as detection. `NEEDS_MORE_INFORMATION` is never a fraud detection. Report it as workload separately. Include precision, recall, F1, FPR, confusion matrices, auto-approval of fraudulent and legitimate campaigns, manual review, information requests, rejection, runtime errors, latency and category metrics. Report component ablations on identical development cases. Offline results are not Gemini, embedding or semantic-RAG results.

## Safety and non-goals

- No production routing/configuration or existing evaluation data/results are modified.
- No Gemini calls, network access, or billing changes.
- No automatic conclusion that a consistent dossier is authentic; issuer confirmation remains `UNAVAILABLE` absent an external verification.
- Do not optimize against any prior 200-, 100-, 150- or V2 120-case benchmark. They are consumed diagnostic records only.
- Do not repair V3 after seeing final-test results; carry any defect into a new development cycle and new test set.

## Reproducibility artifacts

Versioned package/config, deterministic generators, development and final protocol documents, paired evaluator, frozen manifests with source/config/dataset hashes, case-level predictions/explanations, ablation results, dependency version list, and a final report. V2 and production source hashes are checked before evaluation.
