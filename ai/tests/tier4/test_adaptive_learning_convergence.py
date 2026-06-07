# tier 4: adaptive weight learner convergence (in-memory, no db)
# skill-dominated hiring should raise skill_weight; experience signal the opposite
# weights stay non-negative and primary trio sums to 1.0

from __future__ import annotations

import copy
import sys
import os
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# minimal in-memory learner mirroring AdaptiveWeightLearner._simple_weight_update

DEFAULT_WEIGHTS: Dict[str, float] = {
    "skill_weight": 0.40,
    "experience_weight": 0.40,
    "education_weight": 0.20,
    "semantic_similarity_weight": 0.0,
}

WEIGHT_KEYS = list(DEFAULT_WEIGHTS.keys())


def _simple_weight_update(
    feedback_data: List[Dict[str, Any]],
    current_weights: Dict[str, float],
    learning_rate: float = 0.1,
) -> Dict[str, float]:
    # same gradient logic as the service, isolated from orm
    hired = [f for f in feedback_data if f.get("hired")]
    not_hired = [f for f in feedback_data if not f.get("hired")]

    if not hired or not not_hired:
        return current_weights.copy()

    def avg(entries: List[Dict], key: str) -> float:
        vals = [e.get(key, 0.0) for e in entries]
        return sum(vals) / len(vals) if vals else 0.0

    hired_avg_skill = avg(hired, "skill_score")
    not_hired_avg_skill = avg(not_hired, "skill_score")
    hired_avg_exp = avg(hired, "experience_score")
    not_hired_avg_exp = avg(not_hired, "experience_score")
    hired_avg_edu = avg(hired, "education_score")
    not_hired_avg_edu = avg(not_hired, "education_score")

    # positive gradient bumps the matching weight
    skill_signal = hired_avg_skill - not_hired_avg_skill
    exp_signal = hired_avg_exp - not_hired_avg_exp
    edu_signal = hired_avg_edu - not_hired_avg_edu

    new_weights = {
        "skill_weight": max(
            0.0, current_weights["skill_weight"] + learning_rate * skill_signal * 0.01
        ),
        "experience_weight": max(
            0.0, current_weights["experience_weight"] + learning_rate * exp_signal * 0.01
        ),
        "education_weight": max(
            0.0, current_weights["education_weight"] + learning_rate * edu_signal * 0.01
        ),
        "semantic_similarity_weight": current_weights["semantic_similarity_weight"],
    }

    # renormalize primary weights to sum to 1.0
    primary_keys = ["skill_weight", "experience_weight", "education_weight"]
    total = sum(new_weights[k] for k in primary_keys)
    if total > 0:
        for k in primary_keys:
            new_weights[k] = new_weights[k] / total

    return new_weights


def _run_rounds(
    feedback_data: List[Dict[str, Any]],
    n_rounds: int,
    learning_rate: float = 0.1,
) -> Dict[str, float]:
    weights = copy.deepcopy(DEFAULT_WEIGHTS)
    for _ in range(n_rounds):
        weights = _simple_weight_update(feedback_data, weights, learning_rate)
    return weights


# synthetic feedback rows

# hires have high skill scores only
SKILL_SIGNAL_FEEDBACK = [
    {"hired": True,  "skill_score": 90.0, "experience_score": 40.0, "education_score": 50.0, "ai_score": 65.0},
    {"hired": True,  "skill_score": 85.0, "experience_score": 35.0, "education_score": 45.0, "ai_score": 62.0},
    {"hired": True,  "skill_score": 92.0, "experience_score": 30.0, "education_score": 55.0, "ai_score": 67.0},
    {"hired": False, "skill_score": 40.0, "experience_score": 80.0, "education_score": 70.0, "ai_score": 58.0},
    {"hired": False, "skill_score": 35.0, "experience_score": 85.0, "education_score": 75.0, "ai_score": 60.0},
    {"hired": False, "skill_score": 30.0, "experience_score": 90.0, "education_score": 65.0, "ai_score": 56.0},
]

# hires have high experience scores only
EXP_SIGNAL_FEEDBACK = [
    {"hired": True,  "skill_score": 40.0, "experience_score": 90.0, "education_score": 45.0, "ai_score": 63.0},
    {"hired": True,  "skill_score": 35.0, "experience_score": 85.0, "education_score": 40.0, "ai_score": 60.0},
    {"hired": True,  "skill_score": 45.0, "experience_score": 92.0, "education_score": 50.0, "ai_score": 65.0},
    {"hired": False, "skill_score": 80.0, "experience_score": 30.0, "education_score": 70.0, "ai_score": 58.0},
    {"hired": False, "skill_score": 85.0, "experience_score": 25.0, "education_score": 65.0, "ai_score": 56.0},
    {"hired": False, "skill_score": 90.0, "experience_score": 20.0, "education_score": 60.0, "ai_score": 60.0},
]

MAX_ROUNDS = 20
MIN_DELTA = 0.01  # at least 1 percentage point of weight shift


class TestAdaptiveLearningConvergence:

    def test_skill_signal_increases_skill_weight(self):
        # skill-heavy hiring feedback should raise skill_weight
        initial = DEFAULT_WEIGHTS["skill_weight"]
        final = _run_rounds(SKILL_SIGNAL_FEEDBACK, MAX_ROUNDS)["skill_weight"]

        assert final >= initial + MIN_DELTA, (
            f"skill_weight should have increased by ≥ {MIN_DELTA} after "
            f"{MAX_ROUNDS} rounds on a skill-dominant signal. "
            f"Initial={initial:.4f}, Final={final:.4f}."
        )

    def test_skill_signal_decreases_experience_weight(self):
        # same signal should drop experience_weight
        initial = DEFAULT_WEIGHTS["experience_weight"]
        final = _run_rounds(SKILL_SIGNAL_FEEDBACK, MAX_ROUNDS)["experience_weight"]

        assert final <= initial - MIN_DELTA, (
            f"experience_weight should have decreased by ≥ {MIN_DELTA} after "
            f"{MAX_ROUNDS} rounds on a skill-dominant signal. "
            f"Initial={initial:.4f}, Final={final:.4f}."
        )

    def test_experience_signal_increases_experience_weight(self):
        # experience-heavy feedback should raise experience_weight
        initial = DEFAULT_WEIGHTS["experience_weight"]
        final = _run_rounds(EXP_SIGNAL_FEEDBACK, MAX_ROUNDS)["experience_weight"]

        assert final >= initial + MIN_DELTA, (
            f"experience_weight should have increased by ≥ {MIN_DELTA} after "
            f"{MAX_ROUNDS} rounds on an experience-dominant signal. "
            f"Initial={initial:.4f}, Final={final:.4f}."
        )

    def test_weights_sum_to_one_after_rounds(self):
        # skill + experience + education always sum to 1.0
        for feedback, label in [
            (SKILL_SIGNAL_FEEDBACK, "skill-dominated"),
            (EXP_SIGNAL_FEEDBACK, "experience-dominated"),
        ]:
            weights = _run_rounds(feedback, MAX_ROUNDS)
            total = (
                weights["skill_weight"]
                + weights["experience_weight"]
                + weights["education_weight"]
            )
            assert abs(total - 1.0) < 1e-6, (
                f"Weights do not sum to 1.0 after {MAX_ROUNDS} rounds "
                f"({label} signal): total={total:.6f}. "
                "Check normalisation in _simple_weight_update."
            )

    def test_weights_non_negative_after_rounds(self):
        # no negative weights after any number of rounds
        for feedback, label in [
            (SKILL_SIGNAL_FEEDBACK, "skill-dominated"),
            (EXP_SIGNAL_FEEDBACK, "experience-dominated"),
        ]:
            weights = _run_rounds(feedback, MAX_ROUNDS)
            for key, val in weights.items():
                assert val >= 0.0, (
                    f"Weight '{key}' is negative ({val:.4f}) after {MAX_ROUNDS} "
                    f"rounds ({label} signal). Check clipping logic."
                )

    def test_single_round_is_not_stuck(self):
        # one round should move at least one weight by >= 0.001
        initial = copy.deepcopy(DEFAULT_WEIGHTS)
        updated = _simple_weight_update(SKILL_SIGNAL_FEEDBACK, initial, learning_rate=0.1)

        any_change = any(
            abs(updated[k] - initial[k]) >= 0.001 for k in WEIGHT_KEYS
        )
        assert any_change, (
            "A single update round produced no meaningful weight change. "
            "The learner may be stuck or the learning rate is too small."
        )

    def test_learning_rate_zero_preserves_weights(self):
        # learning_rate=0 should leave weights untouched
        initial = copy.deepcopy(DEFAULT_WEIGHTS)
        updated = _simple_weight_update(SKILL_SIGNAL_FEEDBACK, initial, learning_rate=0.0)

        for key in WEIGHT_KEYS:
            assert abs(updated[key] - initial[key]) < 1e-9, (
                f"Weight '{key}' changed with learning_rate=0: "
                f"{initial[key]:.6f} → {updated[key]:.6f}."
            )
