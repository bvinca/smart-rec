# skill gap viz - alignment between job requirements and candidate skills
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import sys
import os

import logging
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_recruiter
from ai.visualization.skill_gap_visualizer import SkillGapVisualizer

router = APIRouter(prefix="/visualization", tags=["visualization"])

_skill_visualizer = None

def get_skill_visualizer():
    # lazy SkillGapVisualizer
    global _skill_visualizer
    if _skill_visualizer is None:
        _skill_visualizer = SkillGapVisualizer()
    return _skill_visualizer


@router.post("/skill-gap", response_model=schemas.SkillGapAnalysisResponse)
def analyze_skill_gap(
    request: schemas.SkillGapAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # skill gap analysis - applicants and recruiters both OK
    applicant = db.query(models.Applicant).filter(
        models.Applicant.id == request.applicant_id
    ).first()
    
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    
    job = db.query(models.Job).filter(models.Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if current_user.role == "applicant":
        application = db.query(models.Application).filter(
            models.Application.applicant_id == applicant.id,
            models.Application.user_id == current_user.id
        ).first()
        if not application:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif current_user.role == "recruiter":
        if job.recruiter_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    visualizer = get_skill_visualizer()
    
    job_text = f"{job.description} {job.requirements or ''}"
    job_skills = visualizer.extract_skills_from_text(job_text)
    
    candidate_skills = applicant.skills or []
    
    if not job_skills:
        job_skills = visualizer.extract_skills_from_text(job.requirements or "")
    
    try:
        result = visualizer.compute_skill_similarity(
            job_skills=job_skills,
            candidate_skills=candidate_skills
        )
        return result
    except Exception as e:
        import traceback
        logger.exception(f"Error analyzing skill gap: {e}")
        logger.info(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing skill gap: {str(e)}"
        )
