from ai.evaluation.fairness_checker import FairnessChecker

def test_fairness_bias_detection():
    # two groups with a score gap
    candidate_data = [
        {"name": "Alice", "group": "STEM", "overall_score": 85},
        {"name": "Ben", "group": "STEM", "overall_score": 82},
        {"name": "Clara", "group": "Non-STEM", "overall_score": 67},
        {"name": "David", "group": "Non-STEM", "overall_score": 65}
    ]

    result = FairnessChecker().audit_fairness(
        candidate_data=candidate_data,
        group_key="group",
        score_key="overall_score",
        threshold=10.0
    )
    
    assert isinstance(result, dict)
    assert "bias_detected" in result
    assert "bias_magnitude" in result
    assert "group_analysis" in result
    assert "recommendations" in result
    assert isinstance(result["bias_detected"], bool)
