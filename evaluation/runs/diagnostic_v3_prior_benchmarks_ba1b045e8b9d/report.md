# Frozen V3 on previously used diagnostic benchmarks

**These are previously used diagnostic datasets, not fresh independent tests.** All three were examined during earlier development cycles; they are synthetic and single-author. V3 was run once here and was not changed afterwards. Gemini disabled (0 calls).

Fraud is the positive class; legitimate **and borderline** cases are negatives (the convention the original protocols for these datasets used). A detection is FLAG_FOR_REVIEW or REJECTED (baseline and V1 also count any emitted red flag, as in their original evaluations). Information requests are not detections.

## fundraising_200 (200 cases; 24 label clusters)

*Note: The baseline heuristic rules were revised after reviewing their errors on this very set (evaluation/README.md), so the baseline row is in-sample and overstates it.*

| Engine | Source | Precision | Recall | F1 | FPR | Legit FPR | Fraud auto-approved | Legit approved | Manual review | Info request | Reject | Runtime errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | saved (offline_heuristic_lexical_200_20261115T150208Z) | 76.2% | 100.0% | 86.5% | 20.8% | 0.0% | 0.0% | 100.0% | 29.5% | 13.0% | 10.0% | 0.0% |
| V1 | executed here (frozen V1) | n/a | 0.0% | 0.0% | 0.0% | 0.0% | 15.0% | 100.0% | 0.0% | 51.5% | 0.0% | 0.0% |
| V2 | saved (diagnostic_v2_prior_benchmarks) | 100.0% | 25.0% | 40.0% | 0.0% | 0.0% | 0.0% | 0.0% | 10.0% | 90.0% | 0.0% | 0.0% |
| V3 | executed here once (frozen V3) | 100.0% | 25.0% | 40.0% | 0.0% | 0.0% | 0.0% | 100.0% | 10.0% | 50.0% | 0.0% | 0.0% |

Category-wise recall / legitimate approval:

| Category | baseline | V1 | V2 | V3 |
|---|---|---|---|---|
| COMMUNITY | 100.0% / 100.0% | 0.0% / 100.0% | 0.0% / 0.0% | 0.0% / 100.0% |
| EDUCATION | 100.0% / 100.0% | 0.0% / 100.0% | 0.0% / 0.0% | 0.0% / 100.0% |
| MEDICAL | 100.0% / 100.0% | 0.0% / 100.0% | 33.3% / 0.0% | 33.3% / 100.0% |

V3 group level: 24/24 clusters homogeneous; detection ICC 1.0; effective n ≈ 24.0. Fraud clusters flagged 2/11 (5–48); recall cluster-bootstrap 95% CI  (0–54).

V3 under the pending-confirmation workflow: states {'ELIGIBLE_PENDING_CONFIRMATION': 80, 'NEEDS_MORE_INFORMATION': 100, 'FLAG_FOR_REVIEW': 20, 'VERIFIED_ACTIVE': 0, 'REJECTED': 0, 'VERIFICATION_ERROR': 0}. Safety — automatic activations 0, fraud pending external confirmation 0. Workload — 20 reviews, 100 information requests, 240 external confirmations.

V3 critical-evidence gaps behind information requests: {'critical_claim_support': 92, 'beneficiary_identity': 82}

## independent_benchmark_100 (100 cases; 100 label clusters)

*Note: Every case is its own scenario group, so clusters equal cases here.*

| Engine | Source | Precision | Recall | F1 | FPR | Legit FPR | Fraud auto-approved | Legit approved | Manual review | Info request | Reject | Runtime errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | saved (independent_benchmark_100_offline_20261115T153504Z) | 40.0% | 95.0% | 56.3% | 95.0% | 97.5% | 5.0% | 2.5% | 95.0% | 0.0% | 0.0% | 0.0% |
| V1 | executed here (frozen V1) | 100.0% | 7.5% | 14.0% | 0.0% | 0.0% | 22.5% | 20.0% | 3.0% | 79.0% | 0.0% | 0.0% |
| V2 | saved (diagnostic_v2_prior_benchmarks) | 75.0% | 7.5% | 13.6% | 1.7% | 0.0% | 0.0% | 0.0% | 4.0% | 96.0% | 0.0% | 0.0% |
| V3 | executed here once (frozen V3) | 75.0% | 15.0% | 25.0% | 3.3% | 0.0% | 20.0% | 15.0% | 8.0% | 77.0% | 0.0% | 0.0% |

Category-wise recall / legitimate approval:

| Category | baseline | V1 | V2 | V3 |
|---|---|---|---|---|
| COMMUNITY | 100.0% / 0.0% | 0.0% / 0.0% | 10.0% / 0.0% | 20.0% / 10.0% |
| EDUCATION | 80.0% / 10.0% | 20.0% / 40.0% | 0.0% / 0.0% | 10.0% / 10.0% |
| MEDICAL | 100.0% / 0.0% | 5.0% / 20.0% | 10.0% / 0.0% | 15.0% / 20.0% |

V3 group level: 100/100 clusters homogeneous; detection ICC None; effective n ≈ None. Fraud clusters flagged 6/40 (7–29); recall cluster-bootstrap 95% CI  (5–28).

V3 under the pending-confirmation workflow: states {'ELIGIBLE_PENDING_CONFIRMATION': 15, 'NEEDS_MORE_INFORMATION': 77, 'FLAG_FOR_REVIEW': 8, 'VERIFIED_ACTIVE': 0, 'REJECTED': 0, 'VERIFICATION_ERROR': 0}. Safety — automatic activations 0, fraud pending external confirmation 8. Workload — 8 reviews, 77 information requests, 45 external confirmations.

V3 critical-evidence gaps behind information requests: {'critical_claim_support': 77}

## independent_test_150 (150 cases; 45 label clusters)

*Note: This set motivated V2; four of its cases are V2/V3 crash-regression tests.*

| Engine | Source | Precision | Recall | F1 | FPR | Legit FPR | Fraud auto-approved | Legit approved | Manual review | Info request | Reject | Runtime errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | saved (independent_test_150_20261115T170654Z) | 14.1% | 20.0% | 16.6% | 81.1% | 75.0% | 80.0% | 25.0% | 56.7% | 0.0% | 0.0% | 0.0% |
| V1 | saved (independent_test_150_20261115T170654Z) | 100.0% | 26.7% | 42.1% | 0.0% | 0.0% | 46.7% | 63.3% | 10.7% | 37.3% | 0.0% | 2.7% |
| V2 | saved (diagnostic_v2_prior_benchmarks) | 100.0% | 16.7% | 28.6% | 0.0% | 0.0% | 0.0% | 0.0% | 6.7% | 93.3% | 0.0% | 0.0% |
| V3 | executed here once (frozen V3) | 100.0% | 16.7% | 28.6% | 0.0% | 0.0% | 60.0% | 75.0% | 6.7% | 39.3% | 0.0% | 0.0% |

Category-wise recall / legitimate approval:

| Category | baseline | V1 | V2 | V3 |
|---|---|---|---|---|
| COMMUNITY | 60.0% / 10.0% | 20.0% / 60.0% | 10.0% / 0.0% | 10.0% / 75.0% |
| EDUCATION | 0.0% / 40.0% | 0.0% / 65.0% | 40.0% / 0.0% | 40.0% / 75.0% |
| MEDICAL | 0.0% / 25.0% | 60.0% / 65.0% | 0.0% / 0.0% | 0.0% / 75.0% |

V3 group level: 22/45 clusters homogeneous; detection ICC 0.8502; effective n ≈ 50.3. Fraud clusters flagged 2/15 (4–38); recall cluster-bootstrap 95% CI  (0–37).

V3 under the pending-confirmation workflow: states {'ELIGIBLE_PENDING_CONFIRMATION': 81, 'NEEDS_MORE_INFORMATION': 59, 'FLAG_FOR_REVIEW': 10, 'VERIFIED_ACTIVE': 0, 'REJECTED': 0, 'VERIFICATION_ERROR': 0}. Safety — automatic activations 0, fraud pending external confirmation 36. Workload — 10 reviews, 59 information requests, 243 external confirmations.

V3 critical-evidence gaps behind information requests: {'beneficiary_identity': 45, 'critical_claim_support': 37}

## Provenance

{
  "v3_package_sha256": "ba1b045e8b9d594891b6aaa4ac8c55b1758f48007a9d0261b177788f2363a7cd",
  "v3_config_sha256": "3835a9c2e20bd30e079664ca775b22f1becf25176ad2b85e4c9bd14598bfc9e9",
  "v2_package_sha256": "a054be91b210c9e22cbc2965e8978a6fda9b07ff10f1893aecc872ba04be6fc6",
  "frozen_v1_and_baseline": {
    "candidate": "f6bba947d5ec1202502ece19e02fdf24b93cdb623a12a59d6eced670118e4eec",
    "baseline_verifier": "3a3b857c8bf658d1400b1a9c92eb1f19a60a405e17ba86199be7298bcd1bc9c8",
    "fraud_rules": "f47e641743d1d66272cf36d6bfa2053245bbf2b68bf15b19075fab41cf97279f",
    "rag": "95b14980be44fd6b658cd4025a0c24a90447a53fb212f42cede257b2f4f71309",
    "config": "edb58aa33fb33fd2dee8dea167b851f524ac1338f0560b13006b6928723d4bb3",
    "schema": "8384f9a64fc3c3fb407409366606fc796adcce5257a02c33de03a7512a962317"
  },
  "v2_saved_predictions": {
    "path": "diagnostic_v2_prior_benchmarks_20261115T205120Z/results.json",
    "sha256": "3ac07d626b29cc42164c4b5d41e2ebd9355f24bbd25f12dc133bc1d77ff27095"
  },
  "runner_sha256": "38373010a0156dc967103a34b0d7aaf22a1778315546dc2fc133826143021d3c",
  "python": "3.9.6"
}
