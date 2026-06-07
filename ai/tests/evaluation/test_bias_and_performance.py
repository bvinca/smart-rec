# bias detection + performance metric smoke tests

import pytest
import sys
import os

# project root on path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.evaluation.fairness_checker import FairnessChecker


class TestBiasAndPerformance:
    
    def test_msd_metric(self):
        # mean score difference on a skewed pair of groups
        checker = FairnessChecker()
        
        candidate_data = [
            {"group": "group_a", "overall_score": 85.0},
            {"group": "group_a", "overall_score": 80.0},
            {"group": "group_b", "overall_score": 70.0},
            {"group": "group_b", "overall_score": 65.0},
        ]
        
        result = checker.comprehensive_fairness_audit(
            candidate_data=candidate_data,
            group_key="group",
            score_key="overall_score",
            threshold=10.0
        )
        
        assert "mean_score_difference" in result
        assert result["mean_score_difference"] > 0
        assert result["bias_detected"] == True
    
    def test_dir_metric(self):
        # disparate impact ratio sanity check
        checker = FairnessChecker()
        
        candidate_data = [
            {"group": "group_a", "overall_score": 85.0},
            {"group": "group_a", "overall_score": 80.0},
            {"group": "group_b", "overall_score": 70.0},
            {"group": "group_b", "overall_score": 65.0},
        ]
        
        result = checker.comprehensive_fairness_audit(
            candidate_data=candidate_data,
            group_key="group",
            score_key="overall_score",
            threshold=10.0
        )
        
        assert "disparate_impact_ratio" in result
        assert 0 <= result["disparate_impact_ratio"] <= 2.0
    
    def test_fairness_threshold(self):
        # small gap should stay under threshold
        checker = FairnessChecker()
        
        candidate_data = [
            {"group": "group_a", "overall_score": 75.0},
            {"group": "group_a", "overall_score": 73.0},
            {"group": "group_b", "overall_score": 72.0},
            {"group": "group_b", "overall_score": 70.0},
        ]
        
        result = checker.comprehensive_fairness_audit(
            candidate_data=candidate_data,
            group_key="group",
            score_key="overall_score",
            threshold=10.0
        )
        
        assert result["bias_magnitude"] < 10.0
    
    def test_statistical_significance(self):
        # p-value field present and bounded
        checker = FairnessChecker()
        
        candidate_data = [
            {"group": "group_a", "overall_score": 85.0},
            {"group": "group_a", "overall_score": 80.0},
            {"group": "group_b", "overall_score": 70.0},
            {"group": "group_b", "overall_score": 65.0},
        ]
        
        result = checker.comprehensive_fairness_audit(
            candidate_data=candidate_data,
            group_key="group",
            score_key="overall_score",
            threshold=10.0
        )
        
        assert "statistical_significance" in result
        assert 0 <= result["statistical_significance"] <= 1.0
    
    def test_accuracy_consistency(self):
        # placeholder until labelled benchmark wired up
        assert True
    
    def test_performance_metrics(self):
        # placeholder for latency/throughput checks
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
