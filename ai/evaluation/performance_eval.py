# stub - real performance metrics live in benchmark/run_benchmark.py
from typing import Dict, List, Any


class PerformanceEvaluator:

    def evaluate_model(self, predictions: List[Dict[str, Any]], ground_truth: List[Dict[str, Any]]) -> Dict[str, float]:
        # stub metrics - real ones live in benchmark runner
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0
        }

