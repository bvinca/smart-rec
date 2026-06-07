# recruiter hiring analytics dashboard
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models, schemas
from app.dependencies import require_recruiter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/", response_model=schemas.AnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter)
):
    # aggregate stats for recruiter's jobs/applications
    total_jobs = db.query(func.count(models.Job.id)).filter(
        models.Job.recruiter_id == current_user.id
    ).scalar()
    
    active_jobs = db.query(func.count(models.Job.id)).filter(
        models.Job.recruiter_id == current_user.id,
        models.Job.status == "active"
    ).scalar()
    
    applications_query = db.query(models.Application).join(models.Job).filter(
        models.Job.recruiter_id == current_user.id
    )
    
    total_applications = applications_query.count()
    pending_applications = applications_query.filter(
        models.Application.status == "pending"
    ).count()
    shortlisted_applications = applications_query.filter(
        models.Application.status == "shortlisted"
    ).count()
    rejected_applications = applications_query.filter(
        models.Application.status == "rejected"
    ).count()
    hired_applications = applications_query.filter(
        models.Application.status == "hired"
    ).count()
    
    avg_score = db.query(func.avg(models.Applicant.overall_score)).join(
        models.Application, models.Application.applicant_id == models.Applicant.id
    ).join(models.Job).filter(
        models.Job.recruiter_id == current_user.id
    ).scalar() or 0.0
    
    # top skills - manual count for sqlite compat
    applicants_with_skills = db.query(models.Applicant).join(
        models.Application, models.Application.applicant_id == models.Applicant.id
    ).join(models.Job).filter(
        models.Job.recruiter_id == current_user.id,
        models.Applicant.skills.isnot(None)
    ).all()
    
    skill_counts = {}
    for applicant in applicants_with_skills:
        if applicant.skills:
            for skill in applicant.skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
    
    top_skills = [
        {"skill": skill, "count": count}
        for skill, count in sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    
    applications_by_job = db.query(
        models.Job.id,
        models.Job.title,
        func.count(models.Application.id).label('application_count')
    ).join(
        models.Application, models.Application.job_id == models.Job.id
    ).filter(
        models.Job.recruiter_id == current_user.id
    ).group_by(models.Job.id, models.Job.title).all()
    
    applications_by_job_list = [
        {"job_id": job_id, "job_title": title, "application_count": count}
        for job_id, title, count in applications_by_job
    ]
    
    return {
        "total_jobs": total_jobs or 0,
        "active_jobs": active_jobs or 0,
        "total_applications": total_applications or 0,
        "pending_applications": pending_applications or 0,
        "shortlisted_applications": shortlisted_applications or 0,
        "rejected_applications": rejected_applications or 0,
        "hired_applications": hired_applications or 0,
        "average_score": float(avg_score),
        "top_skills": top_skills,
        "applications_by_job": applications_by_job_list
    }
