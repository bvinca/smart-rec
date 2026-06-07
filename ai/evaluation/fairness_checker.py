# Fairness auditor - MSD, DIR, SPD. The three metrics the eval chapter uses.
#   MSD: gap between highest and lowest group mean score (want < 10 pts)
#   DIR: selection-rate ratio across groups (four-fifths rule, want 0.8-1.25)
#   SPD: max minus min selection rate (want near 0)
# pandas/scipy nice to have - pure-Python fallbacks below if missing.
# Returns fairness_status: fair | warning | bias_detected.
# Won't crash on junk input (one group, NaN, etc.) - that's on purpose.

from __future__ import annotations

import logging
import math
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional import
    import pandas as pd  # type: ignore
    _PANDAS = True
except Exception:  # pragma: no cover
    pd = None  # type: ignore
    _PANDAS = False

try:  # pragma: no cover - optional import
    from scipy import stats as _scipy_stats  # type: ignore
    _SCIPY = True
except Exception:  # pragma: no cover
    _scipy_stats = None  # type: ignore
    _SCIPY = False


_FAIR = "fair"
_WARNING = "warning"
_BIAS = "bias_detected"


class FairnessChecker:
    # compute MSD / DIR / SPD on a list of candidate dicts

    # public entry points
    def audit_fairness(
        self,
        candidate_data: List[Dict[str, Any]],
        group_key: str = "group",
        score_key: str = "overall_score",
        threshold: float = 10.0,
    ) -> Dict[str, Any]:
        # group-mean audit, MSD as the primary signal
        if not candidate_data or len(candidate_data) < 2:
            return self._empty_result(
                threshold,
                message="Need at least two candidates to perform a fairness audit.",
            )

        groups = self._group_scores(candidate_data, group_key, score_key)
        if not groups:
            return self._empty_result(
                threshold,
                message=f"No usable scores for group_key='{group_key}'.",
            )

        group_means = {name: mean(scores) for name, scores in groups.items()}
        msd = max(group_means.values()) - min(group_means.values())
        bias_detected = msd > threshold

        statistical_significance = self._statistical_significance(groups)
        group_analysis = {
            name: {
                "mean_score": round(group_means[name], 2),
                "std_dev": round(stdev(scores), 2) if len(scores) > 1 else 0.0,
                "count": len(scores),
            }
            for name, scores in groups.items()
        }

        return {
            "bias_detected": bias_detected,
            "bias_magnitude": round(msd, 2),
            "group_analysis": group_analysis,
            "recommendations": self._recommendations(bias_detected, msd, group_means, threshold),
            "statistical_significance": round(statistical_significance, 3),
            "threshold_used": threshold,
            "message": self._message(bias_detected, msd, threshold),
        }

    # MSD / DIR / SPD - each callable standalone
    def mean_score_difference(
        self,
        candidate_data: List[Dict[str, Any]],
        group_col: str = "group",
        score_col: str = "overall_score",
    ) -> float:
        groups = self._group_scores(candidate_data, group_col, score_col)
        if len(groups) < 2:
            return 0.0
        means = [mean(scores) for scores in groups.values()]
        return round(max(means) - min(means), 2)

    def disparate_impact_ratio(
        self,
        candidate_data: List[Dict[str, Any]],
        group_col: str = "group",
        score_col: str = "overall_score",
        threshold: float = 70.0,
    ) -> float:
        rates = self._selection_rates(candidate_data, group_col, score_col, threshold)
        if len(rates) < 2:
            return 1.0
        max_rate = max(rates.values())
        min_rate = min(rates.values())
        if max_rate == 0:
            return 1.0
        return round(min_rate / max_rate, 3)

    def statistical_parity_difference(
        self,
        candidate_data: List[Dict[str, Any]],
        group_col: str = "group",
        score_col: str = "overall_score",
        threshold: float = 70.0,
    ) -> float:
        rates = self._selection_rates(candidate_data, group_col, score_col, threshold)
        if len(rates) < 2:
            return 0.0
        return round(max(rates.values()) - min(rates.values()), 3)

    # full audit - all three metrics + overall fairness_status verdict
    def comprehensive_fairness_audit(
        self,
        candidate_data: List[Dict[str, Any]],
        group_key: str = "group",
        score_key: str = "overall_score",
        threshold: float = 10.0,
        pass_threshold: float = 70.0,
    ) -> Dict[str, Any]:
        base_audit = self.audit_fairness(
            candidate_data, group_key=group_key, score_key=score_key, threshold=threshold
        )
        msd = self.mean_score_difference(candidate_data, group_key, score_key)
        dir_value = self.disparate_impact_ratio(
            candidate_data, group_key, score_key, pass_threshold
        )
        spd = self.statistical_parity_difference(
            candidate_data, group_key, score_key, pass_threshold
        )

        status = self._status(base_audit["bias_detected"], msd, dir_value, threshold)

        recommendations: List[str] = list(base_audit.get("recommendations", []))
        if msd > threshold:
            recommendations.append(
                f"Mean Score Difference ({msd:.2f}) exceeds the {threshold}-point threshold."
            )
        if dir_value < 0.8:
            recommendations.append(
                f"Disparate Impact Ratio ({dir_value:.3f}) is below 0.8 (four-fifths rule)."
            )
        elif dir_value > 1.25:
            recommendations.append(
                f"Disparate Impact Ratio ({dir_value:.3f}) is above 1.25 (reverse adverse impact)."
            )

        if status == _FAIR:
            recommendations.append("All three metrics within acceptable ranges.")

        return {
            **base_audit,
            "mean_score_difference": msd,
            "disparate_impact_ratio": dir_value,
            "statistical_parity_difference": spd,
            "fairness_status": status,
            "recommendations": recommendations,
            "candidates_analysed": len(candidate_data),
            "group_key": group_key,
            "metrics_summary": {
                "msd_target": "< 10 points",
                "msd_actual": f"{msd:.2f}",
                "msd_status": "pass" if msd <= threshold else "fail",
                "dir_target": "0.8 - 1.25",
                "dir_actual": f"{dir_value:.3f}",
                "dir_status": "pass" if 0.8 <= dir_value <= 1.25 else "fail",
                "spd_target": "close to 0",
                "spd_actual": f"{spd:.3f}",
            },
        }

    # internals
    @staticmethod
    def _group_scores(
        candidate_data: List[Dict[str, Any]],
        group_col: str,
        score_col: str,
    ) -> Dict[str, List[float]]:
        groups: Dict[str, List[float]] = {}
        for row in candidate_data:
            group = row.get(group_col)
            score = row.get(score_col)
            if group is None or score is None:
                continue
            try:
                value = float(score)
            except (TypeError, ValueError):
                continue
            if math.isnan(value):
                continue
            groups.setdefault(str(group), []).append(value)
        # drop empty buckets so we never compute a "difference" off nothing
        return {name: values for name, values in groups.items() if values}

    @classmethod
    def _selection_rates(
        cls,
        candidate_data: List[Dict[str, Any]],
        group_col: str,
        score_col: str,
        pass_threshold: float,
    ) -> Dict[str, float]:
        groups = cls._group_scores(candidate_data, group_col, score_col)
        rates = {}
        for name, scores in groups.items():
            if not scores:
                continue
            passes = sum(1 for s in scores if s >= pass_threshold)
            rates[name] = passes / len(scores)
        return rates

    @staticmethod
    def _statistical_significance(groups: Dict[str, List[float]]) -> float:
        # 1 - p_value of a Welch t-test between the top and bottom groups
        if len(groups) < 2:
            return 0.0
        means = {name: mean(values) for name, values in groups.items()}
        max_group = max(means, key=means.get)
        min_group = min(means, key=means.get)
        if max_group == min_group:
            return 0.0
        max_scores = groups[max_group]
        min_scores = groups[min_group]
        if len(max_scores) < 2 or len(min_scores) < 2:
            return 0.0
        if _SCIPY:
            try:
                _t, p_value = _scipy_stats.ttest_ind(max_scores, min_scores, equal_var=False)
                if math.isnan(p_value):
                    return 0.0
                return float(1 - p_value)
            except Exception:  # pragma: no cover - numerical error
                logger.exception("scipy t-test failed; falling back to mean-diff proxy.")
        # no scipy - coarse proxy scaling mean diff into [0, 1]
        diff = abs(mean(max_scores) - mean(min_scores))
        return float(min(0.99, diff / 100.0))

    @staticmethod
    def _recommendations(
        bias_detected: bool,
        msd: float,
        group_means: Dict[str, float],
        threshold: float,
    ) -> List[str]:
        recs: List[str] = []
        if bias_detected:
            recs.append(
                f"Potential bias detected: {msd:.2f}-point gap between groups (threshold {threshold})."
            )
            recs.append("Review scoring criteria and consider blind screening for the affected groups.")
        else:
            recs.append(
                f"No significant bias detected: gap is {msd:.2f} points (within {threshold})."
            )
        if group_means:
            top = max(group_means, key=group_means.get)
            bottom = min(group_means, key=group_means.get)
            recs.append(f"Highest mean: {top} ({group_means[top]:.1f}).")
            recs.append(f"Lowest mean: {bottom} ({group_means[bottom]:.1f}).")
        return recs

    @staticmethod
    def _message(bias_detected: bool, msd: float, threshold: float) -> str:
        if bias_detected:
            return (
                f"Potential bias detected: {msd:.2f}-point gap exceeds threshold {threshold}. "
                "Review scoring criteria."
            )
        return f"No significant bias detected ({msd:.2f}-point gap, threshold {threshold})."

    @staticmethod
    def _status(
        bias_detected: bool,
        msd: float,
        dir_value: float,
        threshold: float,
    ) -> str:
        if bias_detected or msd > threshold:
            return _BIAS
        if msd > threshold * 0.7 or dir_value < 0.8 or dir_value > 1.25:
            return _WARNING
        return _FAIR

    @staticmethod
    def _empty_result(threshold: float, message: str) -> Dict[str, Any]:
        return {
            "bias_detected": False,
            "bias_magnitude": 0.0,
            "group_analysis": {},
            "recommendations": [message],
            "statistical_significance": 0.0,
            "threshold_used": threshold,
            "message": message,
        }
