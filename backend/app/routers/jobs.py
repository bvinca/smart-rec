# job CRUD + AI JD enhancement
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import sys
import os

import logging
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_recruiter
from ai.enhancement.job_description_enhancer import JobDescriptionEnhancer

router = APIRouter(prefix="/jobs", tags=["jobs"])

_job_enhancer = None

def get_job_enhancer():
    # lazy JobDescriptionEnhancer
    global _job_enhancer
    if _job_enhancer is None:
        _job_enhancer = JobDescriptionEnhancer()
    return _job_enhancer


@router.post("/", response_model=schemas.Job)
def create_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # new job posting - recruiter only
    db_job = models.Job(**job.dict(), recruiter_id=current_user.id)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@router.get("/", response_model=List[schemas.Job])
def get_jobs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # list jobs - recruiters see own, applicants see active
    if current_user.role == "recruiter":
        jobs = db.query(models.Job).filter(
            models.Job.recruiter_id == current_user.id
        ).offset(skip).limit(limit).all()
    else:
        jobs = db.query(models.Job).filter(
            models.Job.status == "active"
        ).offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=schemas.Job)
def get_job(job_id: int, db: Session = Depends(get_db)):
    # one job by id
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=schemas.Job)
def update_job(
    job_id: int,
    job_update: schemas.JobUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # update own job - recruiter only
    db_job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.recruiter_id == current_user.id
    ).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = job_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_job, field, value)
    
    db.commit()
    db.refresh(db_job)
    return db_job


@router.post("/{job_id}/enhance", response_model=schemas.JobDescriptionEnhancementResponse)
def enhance_job_description(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # AI JD enhancement - bias/clarity pass - own jobs only
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.recruiter_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    enhancer = get_job_enhancer()
    
    try:
        result = enhancer.enhance_job_description(
            job_description=job.description,
            job_title=job.title
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


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # delete own job - recruiter only
    db_job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.recruiter_id == current_user.id
    ).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db.delete(db_job)
    db.commit()
    return {"message": "Job deleted successfully"}
