# Evaluation - fairness (MSD/DIR/SPD), ranking metrics, LLM evaluator. Lazy imports.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .evaluator import CandidateEvaluator  # noqa: F401
    from .fairness_checker import FairnessChecker  # noqa: F401
    from .performance_eval import PerformanceEvaluator  # noqa: F401
    from .ranking_metrics import RankingMetrics  # noqa: F401

__all__ = [
    "CandidateEvaluator",
    "FairnessChecker",
    "PerformanceEvaluator",
    "RankingMetrics",
]


def __getattr__(name: str) -> Any:
    if name == "FairnessChecker":
        return importlib.import_module(".fairness_checker", __name__).FairnessChecker
    if name == "PerformanceEvaluator":
        return importlib.import_module(".performance_eval", __name__).PerformanceEvaluator
    if name == "RankingMetrics":
        return importlib.import_module(".ranking_metrics", __name__).RankingMetrics
    if name == "CandidateEvaluator":
        return importlib.import_module(".evaluator", __name__).CandidateEvaluator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
