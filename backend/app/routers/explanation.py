# XAI endpoints - attributions + narrative for recruiters/applicants
# re-scores on demand so counterfactuals stay fresh after weight drift

from __future__ import annotations

import logging
import os
import sys

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from ai.explanation.xai_explainer import XAIExplainer  # noqa: E402

from app import models, schemas  # noqa: E402
from app.database import get_db  # noqa: E402
from app.dependencies import get_current_user  # noqa: E402
from app.services.scoring_service import ScoringService  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/explanation", tags=["explanation"])

_explainer: XAIExplainer | None = None


def _get_explainer() -> XAIExplainer:
    global _explainer
    if _explainer is None:
        _explainer = XAIExplainer()
    return _explainer


@router.post("/scoring", response_model=schemas.XAIExplanationResponse)
def explain_scoring(
    request: schemas.XAIExplanationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # LIME/SHAP-style attributions plus plain-English narrative
    applicant = db.query(models.Applicant).filter(
        models.Applicant.id == request.applicant_id
    ).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    job_id = request.job_id or applicant.job_id
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if current_user.role == "applicant":
        application = db.query(models.Application).filter(
            models.Application.applicant_id == applicant.id,
            models.Application.user_id == current_user.id,
        ).first()
        if not application:
            raise HTTPException(status_code=403, detail="Not authorised")
    elif current_user.role == "recruiter":
        if job.recruiter_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorised")
    else:  # pragma: no cover - guarded by router
        raise HTTPException(status_code=403, detail="Not authorised")

    # fresh skill match against live JD - counterfactuals stay current
    scoring_service = ScoringService(db=db)
    fresh = scoring_service.calculate_scores(
        resume_text=applicant.resume_text or "",
        job_description=job.description or "",
        job_requirements=job.requirements or "",
        applicant_skills=applicant.skills or [],
        applicant_experience_years=applicant.experience_years or 0.0,
        applicant_education=applicant.education or [],
        applicant_work_experience=applicant.work_experience or [],
        recruiter_id=job.recruiter_id,
        job_id=job.id,
        use_adaptive_weights=True,
    )

    scores = {
        "skill_score": applicant.skill_score or fresh["skill_score"],
        "experience_score": applicant.experience_score or fresh["experience_score"],
        "education_score": applicant.education_score or fresh["education_score"],
        "match_score": applicant.match_score or fresh["match_score"],
        "overall_score": applicant.overall_score or fresh["overall_score"],
    }

    explainer = _get_explainer()
    try:
        result = explainer.explain_scoring(
            resume_text=applicant.resume_text or "",
            job_description=job.description or "",
            scores=scores,
            candidate_skills=applicant.skills or [],
            candidate_experience_years=applicant.experience_years or 0.0,
            weights=fresh["weights_used"],
            matched_skills=fresh["matched_skills"],
            missing_skills=fresh["missing_skills"],
        )
        return result
    except Exception:
        logger.exception("XAI explanation failed for applicant %s", request.applicant_id)
        raise HTTPException(status_code=500, detail="Failed to generate explanation.")
