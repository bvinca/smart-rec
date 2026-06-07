# adaptive learning service - nudges scoring weights from hire/reject decisions
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
import sys
import os

import logging
logger = logging.getLogger(__name__)

# add the repo root so `ai/` imports resolve when running from backend/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.info("numpy not available. Install with: pip install numpy")

try:
    from sklearn.linear_model import LinearRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("scikit-learn not available. Install with: pip install scikit-learn")

from app.models import ScoringWeights, Application, Applicant


# default weights: 40/40/20 skills/experience/education.
# semantic similarity is folded into the hybrid scorer, so standalone weight = 0.0.
DEFAULT_WEIGHTS = {
    "skill_weight": 0.40,
    "experience_weight": 0.40,
    "education_weight": 0.20,
    "semantic_similarity_weight": 0.0,
}


class AdaptiveWeightLearner:
    # learns scoring weights from recruiter feedback.
    # uses gradient/linear-regression updates over (component score → hired).

    def __init__(self, db: Session):
        self.db = db

    def get_weights(
        self,
        recruiter_id: Optional[int] = None,
        job_id: Optional[int] = None
    ) -> Dict[str, float]:
        # look up weights for the most specific (recruiter, job) scope we
        # have. fall back to DEFAULT_WEIGHTS when nothing exists.
        query = self.db.query(ScoringWeights)

        if recruiter_id and job_id:
            # most specific: recruiter + job
            weights = query.filter(
                ScoringWeights.recruiter_id == recruiter_id,
                ScoringWeights.job_id == job_id
            ).first()
        elif recruiter_id:
            weights = query.filter(
                ScoringWeights.recruiter_id == recruiter_id,
                ScoringWeights.job_id.is_(None)
            ).first()
        elif job_id:
            weights = query.filter(
                ScoringWeights.recruiter_id.is_(None),
                ScoringWeights.job_id == job_id
            ).first()
        else:
            # global
            weights = query.filter(
                ScoringWeights.recruiter_id.is_(None),
                ScoringWeights.job_id.is_(None)
            ).first()
        
        if weights:
            return {
                "skill_weight": float(weights.skill_weight),
                "experience_weight": float(weights.experience_weight),
                "education_weight": float(weights.education_weight),
                "semantic_similarity_weight": float(weights.semantic_similarity_weight)
            }
        
        return DEFAULT_WEIGHTS.copy()
    
    def update_weights(
        self,
        feedback_data: List[Dict[str, Any]],
        recruiter_id: Optional[int] = None,
        job_id: Optional[int] = None,
        learning_rate: float = 0.1
    ) -> Dict[str, float]:
        # update weights from a batch of feedback entries.
        # each entry needs at least {ai_score, hired}; component scores
        # (skill/experience/education/semantic) sharpen the signal when present.
        # learning_rate is the blend factor between old and new weights.
        if not feedback_data or len(feedback_data) < 2:
            # need at least 2 points to fit anything meaningful
            return self.get_weights(recruiter_id, job_id)

        current_weights = self.get_weights(recruiter_id, job_id)

        if not SKLEARN_AVAILABLE or not NUMPY_AVAILABLE:
            # no sklearn/numpy → rule-based fallback
            return self._simple_weight_update(feedback_data, current_weights, learning_rate)

        # ML path
        try:
            X = []
            y = []

            for entry in feedback_data:
                ai_score = entry.get('ai_score', 0)
                hired = 1 if entry.get('hired', False) else 0

                # use component scores when present, otherwise back-estimate from ai_score
                skill_score = entry.get('skill_score', ai_score * 0.4)
                exp_score = entry.get('experience_score', ai_score * 0.3)
                edu_score = entry.get('education_score', ai_score * 0.1)
                semantic_score = entry.get('semantic_score', ai_score * 0.2)

                X.append([skill_score, exp_score, edu_score, semantic_score])
                y.append(hired)

            X = np.array(X)
            y = np.array(y)

            # straight linear regression on (components → hired)
            model = LinearRegression()
            model.fit(X, y)

            coefficients = model.coef_

            # normalise |coefs| to sum 1.0
            total = np.sum(np.abs(coefficients))
            if total > 0:
                normalized_coefs = np.abs(coefficients) / total
            else:
                # all-zero coefs → fall back to 40/40/20 (semantic 0)
                normalized_coefs = np.array([0.4, 0.4, 0.2, 0.0])

            # blend old + new via learning_rate
            new_weights = {
                "skill_weight": float(
                    current_weights["skill_weight"] * (1 - learning_rate) +
                    normalized_coefs[0] * learning_rate
                ),
                "experience_weight": float(
                    current_weights["experience_weight"] * (1 - learning_rate) +
                    normalized_coefs[1] * learning_rate
                ),
                "education_weight": float(
                    current_weights["education_weight"] * (1 - learning_rate) +
                    normalized_coefs[2] * learning_rate
                ),
                "semantic_similarity_weight": float(
                    current_weights["semantic_similarity_weight"] * (1 - learning_rate) +
                    normalized_coefs[3] * learning_rate
                )
            }
            
            # final renormalise - blend can drift from sum=1
            total = sum(new_weights.values())
            if total > 0:
                for key in new_weights:
                    new_weights[key] /= total

            self._save_weights(new_weights, recruiter_id, job_id)

            return new_weights

        except Exception as e:
            logger.exception(f"AdaptiveWeightLearner: Error in ML update: {e}")
            # ML blew up → simple fallback
            return self._simple_weight_update(feedback_data, current_weights, learning_rate)

    def _simple_weight_update(
        self,
        feedback_data: List[Dict[str, Any]],
        current_weights: Dict[str, float],
        learning_rate: float
    ) -> Dict[str, float]:
        # rule-based fallback when sklearn isn't installed
        hired_scores = {
            "skill": [],
            "experience": [],
            "education": [],
            "semantic": []
        }
        not_hired_scores = {
            "skill": [],
            "experience": [],
            "education": [],
            "semantic": []
        }
        
        for entry in feedback_data:
            is_hired = entry.get('hired', False)
            target = hired_scores if is_hired else not_hired_scores
            
            ai_score = entry.get('ai_score', 0)
            target["skill"].append(entry.get('skill_score', ai_score * 0.4))
            target["experience"].append(entry.get('experience_score', ai_score * 0.3))
            target["education"].append(entry.get('education_score', ai_score * 0.1))
            target["semantic"].append(entry.get('semantic_score', ai_score * 0.2))
        
        # bump weights for components where the hired group scored higher
        if hired_scores["skill"] and not_hired_scores["skill"]:
            skill_diff = np.mean(hired_scores["skill"]) - np.mean(not_hired_scores["skill"]) if NUMPY_AVAILABLE else 0
            exp_diff = np.mean(hired_scores["experience"]) - np.mean(not_hired_scores["experience"]) if NUMPY_AVAILABLE else 0
            edu_diff = np.mean(hired_scores["education"]) - np.mean(not_hired_scores["education"]) if NUMPY_AVAILABLE else 0
            sem_diff = np.mean(hired_scores["semantic"]) - np.mean(not_hired_scores["semantic"]) if NUMPY_AVAILABLE else 0

            adjustments = {
                "skill_weight": skill_diff * learning_rate / 100.0,
                "experience_weight": exp_diff * learning_rate / 100.0,
                "education_weight": edu_diff * learning_rate / 100.0,
                "semantic_similarity_weight": sem_diff * learning_rate / 100.0
            }
            
            new_weights = {
                "skill_weight": max(0.20, min(0.60, current_weights["skill_weight"] + adjustments["skill_weight"])),
                "experience_weight": max(0.20, min(0.60, current_weights["experience_weight"] + adjustments["experience_weight"])),
                "education_weight": max(0.05, min(0.40, current_weights["education_weight"] + adjustments["education_weight"])),
                # let this fall all the way to 0 so the 40/40/20 default is reachable
                "semantic_similarity_weight": max(0.00, min(0.30, current_weights["semantic_similarity_weight"] + adjustments["semantic_similarity_weight"])),
            }

            total = sum(new_weights.values())
            if total > 0:
                for key in new_weights:
                    new_weights[key] /= total

            self._save_weights(new_weights, None, None)
            return new_weights

        return current_weights

    def _save_weights(
        self,
        weights: Dict[str, float],
        recruiter_id: Optional[int],
        job_id: Optional[int]
    ):
        # upsert weights for the (recruiter, job) scope
        query = self.db.query(ScoringWeights)
        
        if recruiter_id and job_id:
            weights_record = query.filter(
                ScoringWeights.recruiter_id == recruiter_id,
                ScoringWeights.job_id == job_id
            ).first()
        elif recruiter_id:
            weights_record = query.filter(
                ScoringWeights.recruiter_id == recruiter_id,
                ScoringWeights.job_id.is_(None)
            ).first()
        elif job_id:
            weights_record = query.filter(
                ScoringWeights.recruiter_id.is_(None),
                ScoringWeights.job_id == job_id
            ).first()
        else:
            weights_record = query.filter(
                ScoringWeights.recruiter_id.is_(None),
                ScoringWeights.job_id.is_(None)
            ).first()
        
        if weights_record:
            weights_record.skill_weight = weights["skill_weight"]
            weights_record.experience_weight = weights["experience_weight"]
            weights_record.education_weight = weights["education_weight"]
            weights_record.semantic_similarity_weight = weights["semantic_similarity_weight"]
            weights_record.iteration_count += 1
        else:
            weights_record = ScoringWeights(
                recruiter_id=recruiter_id,
                job_id=job_id,
                skill_weight=weights["skill_weight"],
                experience_weight=weights["experience_weight"],
                education_weight=weights["education_weight"],
                semantic_similarity_weight=weights["semantic_similarity_weight"],
                iteration_count=1
            )
            self.db.add(weights_record)
        
        self.db.commit()
    
    def collect_feedback_data(
        self,
        recruiter_id: Optional[int] = None,
        job_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        # gather (decision, scores) tuples from applications that have a
        # final hire/reject + an AI score at the decision moment
        query = self.db.query(Application).join(Applicant).filter(
            Application.hire_decision.isnot(None),  # decisions only
            Application.ai_score_at_decision.isnot(None)  # AI score must be recorded
        )

        if recruiter_id:
            # restrict to this recruiter's jobs
            query = query.join(Applicant.job).filter(Applicant.job.has(recruiter_id=recruiter_id))
        
        if job_id:
            query = query.filter(Application.job_id == job_id)
        
        applications = query.order_by(Application.updated_at.desc()).limit(limit).all()
        
        feedback_data = []
        for app in applications:
            applicant = app.applicant_id and self.db.query(Applicant).filter(Applicant.id == app.applicant_id).first()
            
            if applicant:
                feedback_data.append({
                    "ai_score": app.ai_score_at_decision or 0,
                    "hired": app.hire_decision or False,
                    "skill_score": applicant.skill_score or 0,
                    "experience_score": applicant.experience_score or 0,
                    "education_score": applicant.education_score or 0,
                    "semantic_score": applicant.match_score or 0,
                    "application_id": app.id
                })
        
        return feedback_data

