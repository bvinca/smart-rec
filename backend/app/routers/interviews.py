# interview scheduling CRUD
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_recruiter

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("/", response_model=schemas.InterviewResponse)
def create_interview(
    interview: schemas.InterviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # schedule interview - recruiter only
    application = db.query(models.Application).filter(
        models.Application.id == interview.application_id
    ).first()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    if job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db_interview = models.Interview(**interview.dict())
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    
    return db_interview


@router.get("/", response_model=List[schemas.InterviewResponse])
def get_interviews(
    application_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # list interviews - scoped by role
    if current_user.role == "applicant":
        query = db.query(models.Interview).join(models.Application).filter(
            models.Application.user_id == current_user.id
        )
        if application_id:
            query = query.filter(models.Interview.application_id == application_id)
    else:
        query = db.query(models.Interview).join(
            models.Application
        ).join(models.Job).filter(
            models.Job.recruiter_id == current_user.id
        )
        if application_id:
            query = query.filter(models.Interview.application_id == application_id)
    
    interviews = query.order_by(models.Interview.scheduled_at).all()
    return interviews


@router.get("/{interview_id}", response_model=schemas.InterviewResponse)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # one interview by id
    interview = db.query(models.Interview).filter(
        models.Interview.id == interview_id
    ).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    application = db.query(models.Application).filter(
        models.Application.id == interview.application_id
    ).first()
    
    if current_user.role == "applicant":
        if application.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
        if job.recruiter_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    return interview


@router.put("/{interview_id}", response_model=schemas.InterviewResponse)
def update_interview(
    interview_id: int,
    interview_update: schemas.InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # update interview - recruiter only
    interview = db.query(models.Interview).filter(
        models.Interview.id == interview_id
    ).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    application = db.query(models.Application).filter(
        models.Application.id == interview.application_id
    ).first()
    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    
    if job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = interview_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(interview, field, value)
    
    db.commit()
    db.refresh(interview)
    return interview


@router.delete("/{interview_id}")
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # cancel interview - recruiter only
    interview = db.query(models.Interview).filter(
        models.Interview.id == interview_id
    ).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    application = db.query(models.Application).filter(
        models.Application.id == interview.application_id
    ).first()
    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    
    if job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(interview)
    db.commit()
    return {"message": "Interview cancelled successfully"}
