# AI enhancement - JD bias cleanup + resume feedback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import sys
import os

import logging
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_recruiter
from ai.enhancement.job_description_enhancer import JobDescriptionEnhancer
from ai.enhancement.resume_analyzer import ResumeAnalyzer

router = APIRouter(prefix="/enhancement", tags=["enhancement"])

_job_enhancer = None
_resume_analyzer = None

def get_job_enhancer():
    # lazy JobDescriptionEnhancer
    global _job_enhancer
    if _job_enhancer is None:
        _job_enhancer = JobDescriptionEnhancer()
    return _job_enhancer

def get_resume_analyzer():
    # lazy ResumeAnalyzer
    global _resume_analyzer
    if _resume_analyzer is None:
        _resume_analyzer = ResumeAnalyzer()
    return _resume_analyzer


@router.post("/job-description", response_model=schemas.JobDescriptionEnhancementResponse)
def enhance_job_description(
    request: schemas.JobDescriptionEnhancementRequest,
    current_user: models.User = Depends(require_recruiter)
):
    # improve JD for bias/clarity - recruiter only
    enhancer = get_job_enhancer()
    
    try:
        result = enhancer.enhance_job_description(
            job_description=request.description,
            job_title=request.title or ""
        )
        return result
    except Exception as e:
        import traceback
        logger.exception(f"Error enhancing job description: {e}")
        logger.info(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error enhancing job description: {str(e)}"
        )


@router.post("/resume-analysis", response_model=schemas.ResumeFeedbackResponse)
def analyze_resume(
    request: schemas.ResumeFeedbackRequest,
    current_user: models.User = Depends(get_current_user)
):
    # resume feedback vs optional JD - both roles
    analyzer = get_resume_analyzer()
    
    try:
        result = analyzer.analyze_resume(
            resume_text=request.resume_text,
            job_description=request.job_description,
            job_requirements=request.job_requirements
        )
        return result
    except Exception as e:
        import traceback
        logger.exception(f"Error analyzing resume: {e}")
        logger.info(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing resume: {str(e)}"
        )
