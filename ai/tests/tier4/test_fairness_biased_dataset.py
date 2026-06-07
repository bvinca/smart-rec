# tier 4: fairness checker on intentionally biased data
# skewed group scores should get flagged; fair data should not

from __future__ import annotations

import sys
import os

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.evaluation.fairness_checker import FairnessChecker  # noqa: E402


# biased: group a ~20 pts higher than group b

BIASED_DATASET = [
    # group a (advantaged)
    {"group": "group_a", "overall_score": 88.0, "name": "Alice"},
    {"group": "group_a", "overall_score": 85.0, "name": "Bob"},
    {"group": "group_a", "overall_score": 82.0, "name": "Carol"},
    {"group": "group_a", "overall_score": 79.0, "name": "Dave"},
    {"group": "group_a", "overall_score": 90.0, "name": "Eve"},
    # group b (disadvantaged, ~20 pt gap)
    {"group": "group_b", "overall_score": 68.0, "name": "Frank"},
    {"group": "group_b", "overall_score": 65.0, "name": "Grace"},
    {"group": "group_b", "overall_score": 62.0, "name": "Heidi"},
    {"group": "group_b", "overall_score": 69.0, "name": "Ivan"},
    {"group": "group_b", "overall_score": 66.0, "name": "Judy"},
]

# fair: similar distributions

FAIR_DATASET = [
    {"group": "group_a", "overall_score": 75.0, "name": "A1"},
    {"group": "group_a", "overall_score": 73.0, "name": "A2"},
    {"group": "group_a", "overall_score": 77.0, "name": "A3"},
    {"group": "group_a", "overall_score": 74.0, "name": "A4"},
    {"group": "group_b", "overall_score": 74.0, "name": "B1"},
    {"group": "group_b", "overall_score": 72.0, "name": "B2"},
    {"group": "group_b", "overall_score": 76.0, "name": "B3"},
    {"group": "group_b", "overall_score": 73.0, "name": "B4"},
]

# gender as group key
GENDER_BIASED_DATASET = [
    {"gender": "M", "overall_score": 84.0, "name": "Male1"},
    {"gender": "M", "overall_score": 81.0, "name": "Male2"},
    {"gender": "M", "overall_score": 86.0, "name": "Male3"},
    {"gender": "M", "overall_score": 83.0, "name": "Male4"},
    {"gender": "F", "overall_score": 64.0, "name": "Female1"},
    {"gender": "F", "overall_score": 61.0, "name": "Female2"},
    {"gender": "F", "overall_score": 66.0, "name": "Female3"},
    {"gender": "F", "overall_score": 62.0, "name": "Female4"},
]


class TestFairnessWithBiasedDataset:
    # checker should catch skew and stay quiet on fair data

    def test_msd_detects_large_gap(self):
        # msd should exceed threshold on biased data
        checker = FairnessChecker()
        result = checker.comprehensive_fairness_audit(
            candidate_data=BIASED_DATASET,
            group_key="group",
            score_key="overall_score",
            threshold=10.0,
        )

        assert result["mean_score_difference"] > 10.0, (
            f"MSD={result['mean_score_difference']:.2f} should be > 10 for a ~20-point gap."
        )
        assert result["bias_detected"] is True, (
            "bias_detected should be True for a ~20-point inter-group gap."
        )

    def test_dir_below_80_percent_rule_for_biased_data(self):
        # dir should fail 4/5 rule on biased data
        checker = FairnessChecker()
        result = checker.comprehensive_fairness_audit(
            candidate_data=BIASED_DATASET,
            group_key="group",
            score_key="overall_score",
            threshold=10.0,
        )

        dir_value = result.get("disparate_impact_ratio", 1.0)
        # group b ~20 pts lower, dir should be < 0.85
        assert dir_value < 0.85, (
            f"DIR={dir_value:.3f} should be < 0.85 for a biased dataset. "
            "The FairnessChecker may not be computing DIR correctly."
        )

    def test_no_false_positive_on_fair_dataset(self):
        # fair dataset should not trigger bias
        checker = FairnessChecker()
        result = checker.comprehensive_fairness_audit(
            candidate_data=FAIR_DATASET,
            group_key="group",
            score_key="overall_score",
            threshold=10.0,
        )

        assert result["bias_magnitude"] < 10.0, (
            f"bias_magnitude={result['bias_magnitude']:.2f} should be < 10 "
            "for a near-equal score distribution."
        )

    def test_gender_bias_detected(self):
        # gender key should work too
        checker = FairnessChecker()
        result = checker.comprehensive_fairness_audit(
            candidate_data=GENDER_BIASED_DATASET,
            group_key="gender",
            score_key="overall_score",
            threshold=10.0,
        )

        assert result["bias_detected"] is True, (
            "Bias should be detected in the gender-biased dataset (M=83, F=63 avg)."
        )

    def test_result_structure_complete(self):
        # audit payload should have all expected keys
        required_keys = {
            "mean_score_difference",
            "disparate_impact_ratio",
            "bias_magnitude",
            "bias_detected",
            "statistical_significance",
        }
        checker = FairnessChecker()
        result = checker.comprehensive_fairness_audit(
            candidate_data=BIASED_DATASET,
            group_key="group",
            score_key="overall_score",
            threshold=10.0,
        )

        missing = required_keys - set(result.keys())
        assert not missing, f"Audit result is missing keys: {missing}"

    def test_bias_magnitude_reflects_actual_gap(self):
        # bias_magnitude within 5 pts of real gap
        checker = FairnessChecker()
        result = checker.comprehensive_fairness_audit(
            candidate_data=BIASED_DATASET,
            group_key="group",
            score_key="overall_score",
            threshold=10.0,
        )

        group_a_avg = sum(
            d["overall_score"] for d in BIASED_DATASET if d["group"] == "group_a"
        ) / 5
        group_b_avg = sum(
            d["overall_score"] for d in BIASED_DATASET if d["group"] == "group_b"
        ) / 5
        actual_gap = abs(group_a_avg - group_b_avg)

        assert abs(result["bias_magnitude"] - actual_gap) <= 5.0, (
            f"bias_magnitude={result['bias_magnitude']:.2f} deviates more than 5 "
            f"from the actual gap ({actual_gap:.2f})."
        )
