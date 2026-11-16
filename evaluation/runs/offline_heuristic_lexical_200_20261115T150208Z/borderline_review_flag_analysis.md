# Offline evaluation: borderline review-flag analysis

Generated: 2026-11-15T15:18:46.835741+00:00

## Scope and method

This read-only analysis joins the saved 200-case offline predictions to the original synthetic JSONL scenarios. It does not modify the dataset, rules, scoring logic, or thresholds. The local heuristic dimensions were recomputed for the five flagged borderline templates using the same `AIVerifierService._verify_with_local_heuristics` method. Gemini generation and embeddings were disabled; retrieval was lexical only.

The label mapping is fraudulent=positive; legitimate and borderline=negative. The offline `flagged` metric means recommendation `FLAG_FOR_REVIEW` or `REJECT`, or any red flag. “Review rate” below means the exact `FLAG_FOR_REVIEW` recommendation.

## Detection and review rates

| Ground truth | Cases | Any-flag detection | Review recommendation | Rejection | Red-flag presence |
|---|---:|---:|---:|---:|---:|
| Fraudulent | 80 | 80/80 (100.0%) | 34/80 (42.5%) | 20/80 (25.0%) | 66/80 (82.5%) |
| Legitimate | 80 | 0/80 (0.0%) | 0/80 (0.0%) | 0/80 (0.0%) | 0/80 (0.0%) |
| Borderline | 40 | 25/40 (62.5%) | 25/40 (62.5%) | 0/40 (0.0%) | 0/40 (0.0%) |

For fraudulent campaigns, all 80 were broadly flagged: 34 were `FLAG_FOR_REVIEW` (42.5%), 20 `REJECT` (25.0%), and 26 `NEEDS_MORE_INFO` with red-flag matches (32.5%). Of the 34 review recommendations, 14 had no red-flag match and 20 had one or more red flags. These action counts overlap with red-flag presence and should not be added. All 80 legitimate campaigns were auto-approved. Of 40 borderline cases, 25 were review-flagged and 15 auto-approved; no borderline case had a red-flag match or rejection.

## The 25 flagged borderline scenarios

All 25 have `FLAG_FOR_REVIEW`, zero red flags, zero attached documents, and zero retrieved evidence. They were not rejected and the engine did not explicitly label them fraudulent. Their missing documents and unresolved claims make a request for manual verification reasonable; the dataset contains no human-review outcome, so it cannot establish how a reviewer would actually decide.

| Template family | Case IDs | N | Score; plausibility / specificity / red-flag / documentation | Heuristics driving review |
|---|---|---:|---|---|
| Inconsistent cardiac estimate | SYN-122, SYN-130, SYN-138, SYN-146, SYN-154 | 5 | 54.0; 30 / 60 / 100 / 25 | The MEDICAL fallback selects the generic surgery benchmark. ₹1.1M exceeds 1.75× its ₹500K maximum, lowering plausibility to 30. The story says the estimate is not itemized; no proof is attached. |
| Third-party recovery/privacy | SYN-123, SYN-131, SYN-139, SYN-147, SYN-155 | 5 | 65.1; 92 / 30 / 100 / 25 | ₹175K is within the generic surgery benchmark (plausibility 92), but no treating facility, clinician, or patient/admission reference is supplied (specificity 30); documentation is 25. Because a beneficiary name is present, the existing missing-name check does not fire. |
| Elevated neurological treatment cost | SYN-124, SYN-132, SYN-140, SYN-148, SYN-156 | 5 | 54.0; 30 / 60 / 100 / 25 | The MEDICAL fallback selects the generic surgery benchmark. ₹4.8M exceeds 1.75× its ₹500K maximum (plausibility 30); the described one-page estimate has no attached evidence or itemized stages. |
| Post-surgery rehabilitation, ₹310K | SYN-127, SYN-135, SYN-143, SYN-151, SYN-159 | 5 | 68.8; 92 / 45 / 100 / 25 | ₹310K is within the generic surgery benchmark (plausibility 92); specificity is 45 and documentation is 25 because no evidence was attached or retrieved. |
| Patient outside city, ₹520K | SYN-128, SYN-136, SYN-144, SYN-152, SYN-160 | 5 | 74.5; 65 / 100 / 100 / 25 | ₹520K is slightly above the generic surgery benchmark maximum (plausibility 65). Specificity is 100, but documentation remains 25 because no estimate or other record is attached. |

All scores fall from 54.0 to 74.5. The fixed thresholds map scores ≥50 and <80 to `FLAG_FOR_REVIEW`, so the result is an escalation for evidence review, not a fraud finding. The binary evaluation nevertheless counts every review flag as a positive prediction; this is why 25 borderline reviews contribute false positives.

## Recurring synthetic patterns and inflation risk

The generator asserts that all 200 story strings are unique, but it varies names, amounts, places, identifiers, and short addenda around a limited set of base narratives. Its construction is:

| Portion | Reused construction |
|---|---|
| 60 legitimate medical | Three story forms cycle over 20 condition/treatment tuples; recognized hospitals, doctors, dates, UHIDs, and estimates recur. |
| 60 fraudulent medical | Six explicit scam narratives repeat ten times each: personal payout, advance fee, miracle cure, forged estimate, prize scam, and untraceable payment. |
| 40 borderline | Eight base templates repeat five times each, with names, BR identifiers, and uncertainty addenda varied. The 25 flags comprise five repeats from each of five templates. |
| 20 legitimate education/social | Five purpose templates repeat four times each. |
| 20 fraudulent education/social | Five fraud templates repeat four times each. |

This creates plausible performance inflation: medical fraud examples contain phrases that closely mirror explicit red-flag patterns, while legitimate medical examples repeatedly use the institution and document cues rewarded by specificity and documentation scoring. The 80/80 observed fraud flag rate is valid for this fixed synthetic set, but is not a real-world recall estimate. The degree of inflation cannot be quantified from this dataset alone. The borderline results are also template-sensitive: the five flagged template families differ from the 15 auto-approved borderline cases, even though all are labeled borderline.

## Provenance

- Predictions analyzed: 200, with 200 unique case IDs. Heuristic recomputation matched the saved score/action for each flagged borderline template.
- No dataset, scoring, or rule changes were made for this analysis.
- Source artifacts: `fundraising_scenarios.jsonl`, this run’s `predictions.csv`, and `results.json`.
- Dataset SHA-256: `cb6d08c426d8ecbfce9c661d9ef32d756ab68a052671c3fadad31d43b1cd3099`.
- Predictions SHA-256: `e908e347dea9dfbe9262fe72f7f5be92cd5eea9414f9d16bdce177fc30f08f60`.
- Heuristic source SHA-256: `3a3b857c8bf658d1400b1a9c92eb1f19a60a405e17ba86199be7298bcd1bc9c8`.
- Fraud-rule source SHA-256: `f47e641743d1d66272cf36d6bfa2053245bbf2b68bf15b19075fab41cf97279f`.
