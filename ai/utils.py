# hybrid scoring + ranking helpers - weighted blend per AI_LAYER_DESIGN.md
from typing import List, Dict, Any, Tuple
import numpy as np


def combine_scores(semantic_score: float, llm_score: float, semantic_weight: float = 0.5) -> float:
    # weighted average: final = w*semantic + (1-w)*llm. Default 50/50.
    llm_weight = 1.0 - semantic_weight
    combined = (semantic_weight * semantic_score) + (llm_weight * llm_score)
    return round(combined, 2)


def normalize_scores(scores: List[float], min_score: float = 0.0, max_score: float = 100.0) -> List[float]:
    # rescale into 0-100 relative to the actual min/max in this batch so candidates
    # get ranked against each other for the specific job posting
    if not scores:
        return []

    # all scores identical - leave as-is
    if len(set(scores)) == 1:
        return scores

    actual_min = min(scores)
    actual_max = max(scores)

    # div-by-zero guard - neutral 50s
    if actual_max == actual_min:
        return [50.0] * len(scores)

    normalized = []
    for score in scores:
        normalized_score = ((score - actual_min) / (actual_max - actual_min)) * 100.0
        normalized.append(round(normalized_score, 2))

    return normalized


def rank_candidates(
    candidates: List[Dict[str, Any]],
    score_key: str = "overall_score",
    ascending: bool = False
) -> List[Dict[str, Any]]:
    # sort by score; default is highest first
    return sorted(candidates, key=lambda x: x.get(score_key, 0), reverse=not ascending)


def calculate_hybrid_scores(
    semantic_scores: Dict[str, float],
    llm_scores: Dict[str, float],
    semantic_weight: float = 0.5
) -> Dict[str, float]:
    # blend semantic + LLM scores key-by-key
    hybrid_scores = {}

    for key in semantic_scores.keys():
        semantic = semantic_scores.get(key, 50.0)
        llm = llm_scores.get(key, 50.0)
        hybrid_scores[key] = combine_scores(semantic, llm, semantic_weight)

    return hybrid_scores


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    # cosine sim, with a numpy-free fallback if numpy isn't around
    try:
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    except ImportError:
        # pure-Python fallback
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)


def similarity_to_score(similarity: float, min_sim: float = -1.0, max_sim: float = 1.0) -> float:
    # squash cosine sim (-1..1) into a 0-100 score
    if max_sim == min_sim:
        return 50.0

    normalized = ((similarity - min_sim) / (max_sim - min_sim)) * 100.0
    return round(max(0.0, min(100.0, normalized)), 2)


def get_score_breakdown(
    semantic_score: float,
    llm_score: float,
    semantic_weight: float = 0.5
) -> Dict[str, Any]:
    # full breakdown - handy when debugging which side drove the combined score
    llm_weight = 1.0 - semantic_weight
    combined = combine_scores(semantic_score, llm_score, semantic_weight)

    return {
        "semantic_score": semantic_score,
        "llm_score": llm_score,
        "semantic_weight": semantic_weight,
        "llm_weight": llm_weight,
        "semantic_contribution": round(semantic_score * semantic_weight, 2),
        "llm_contribution": round(llm_score * llm_weight, 2),
        "combined_score": combined
    }

