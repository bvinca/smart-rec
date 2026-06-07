# fairness auditor tests
# mirrors ch5 contract: msd < 10 and dir in [0.8, 1.25] means fair; obvious bias gets flagged

from __future__ import annotations

from ai.evaluation.fairness_checker import FairnessChecker


def _candidate(group: str, score: float) -> dict:
    return {"group": group, "overall_score": score}


def test_balanced_groups_report_fair():
    checker = FairnessChecker()
    data = [
        _candidate("A", 70),
        _candidate("A", 72),
        _candidate("A", 68),
        _candidate("B", 71),
        _candidate("B", 69),
        _candidate("B", 73),
    ]
    result = checker.comprehensive_fairness_audit(data)
    assert result["fairness_status"] == "fair"
    assert result["mean_score_difference"] < 5
    assert 0.8 <= result["disparate_impact_ratio"] <= 1.25
    assert result["statistical_parity_difference"] < 0.2


def test_obvious_bias_is_detected():
    checker = FairnessChecker()
    data = [
        _candidate("A", 90),
        _candidate("A", 88),
        _candidate("A", 92),
        _candidate("B", 60),
        _candidate("B", 58),
        _candidate("B", 62),
    ]
    result = checker.comprehensive_fairness_audit(data)
    assert result["fairness_status"] == "bias_detected"
    assert result["mean_score_difference"] > 10
    # group a clears 70, group b does not, so dir should tank
    assert result["disparate_impact_ratio"] < 0.5


def test_handles_single_group_gracefully():
    checker = FairnessChecker()
    data = [_candidate("only", 75), _candidate("only", 72)]
    result = checker.comprehensive_fairness_audit(data)
    assert result["bias_detected"] is False
    assert result["mean_score_difference"] == 0.0


def test_handles_empty_input():
    checker = FairnessChecker()
    result = checker.comprehensive_fairness_audit([])
    assert result["bias_detected"] is False
    assert result["candidates_analysed"] == 0
