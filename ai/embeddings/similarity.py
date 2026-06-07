# Cosine similarity + helpers to map it to a 0-100 match score
from typing import List, Dict, Any
import math

# numpy optional - pure-Python fallback if missing
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None


class SimilarityCalculator:

    @staticmethod
    def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
        if not embedding1 or not embedding2:
            return 0.0

        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same dimension for cosine similarity.")

        if NUMPY_AVAILABLE:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
        else:
            # pure Python fallback
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            norm1 = math.sqrt(sum(a * a for a in embedding1))
            norm2 = math.sqrt(sum(b * b for b in embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    @staticmethod
    def calculate_match_score(
        resume_embedding: List[float],
        job_embedding: List[float]
    ) -> float:
        # squish cosine (-1..1) into a 0-100 score
        similarity = SimilarityCalculator.cosine_similarity(resume_embedding, job_embedding)
        return float((similarity + 1) * 50)

    @staticmethod
    def rank_candidates(
        resume_embeddings: List[List[float]],
        job_embedding: List[float]
    ) -> List[Dict[str, Any]]:
        # rank by semantic similarity to the job, highest first
        candidates_with_scores = []

        for idx, resume_emb in enumerate(resume_embeddings):
            score = SimilarityCalculator.calculate_match_score(resume_emb, job_embedding)
            candidates_with_scores.append({
                "candidate_index": idx,
                "match_score": score,
                "similarity": SimilarityCalculator.cosine_similarity(resume_emb, job_embedding)
            })

        candidates_with_scores.sort(key=lambda x: x["match_score"], reverse=True)

        return candidates_with_scores

