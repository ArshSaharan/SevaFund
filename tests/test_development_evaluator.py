from evaluation.evaluate_development_candidate import binary_metrics, build_retrieval_query


def test_binary_metrics_use_fraud_positive_and_review_queue_burden():
    rows = [
        {"ground_truth": "fraudulent", "flagged": True, "recommendation": "FLAG_FOR_REVIEW"},
        {"ground_truth": "fraudulent", "flagged": False, "recommendation": "AUTO_APPROVE"},
        {"ground_truth": "legitimate", "flagged": True, "recommendation": "NEEDS_MORE_INFO"},
        {"ground_truth": "legitimate", "flagged": False, "recommendation": "AUTO_APPROVE"},
    ]
    result = binary_metrics(rows)
    assert result["confusion_matrix"] == {"true_positive": 1, "false_positive": 1, "false_negative": 1, "true_negative": 1}
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["false_positive_rate"] == 0.5
    assert result["review_burden_rate"] == 0.5


def test_runner_contract_compares_same_ids_and_fraud_labels():
    from evaluation.evaluate_development_candidate import assert_paired
    baseline = [{"case_id": "D-1", "ground_truth": "fraudulent"}]
    candidate = [{"case_id": "D-1", "ground_truth": "fraudulent"}]
    assert_paired(baseline, candidate)


def test_candidate_retrieval_query_matches_baseline_fields():
    case = {"title": "Care", "category": "MEDICAL", "beneficiary_name": "Asha Rao",
            "city": "Pune", "state": "Maharashtra", "story": "Clinic support", "goal_amount": 50000}
    assert build_retrieval_query(case) == "Care MEDICAL Asha Rao Pune, Maharashtra Clinic support ₹50,000"
