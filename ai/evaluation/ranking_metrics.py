# stub - real NDCG is in benchmark/run_benchmark.py
from typing import List, Dict, Any


class RankingMetrics:

    def calculate_ndcg(self, ranked_candidates: List[Dict[str, Any]], ground_truth: List[int]) -> float:
        # TODO
        return 0.0

    def calculate_diversity(self, ranked_candidates: List[Dict[str, Any]]) -> float:
        # TODO
        return 0.0

