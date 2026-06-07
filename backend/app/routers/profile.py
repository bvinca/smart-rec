# profile, resume, voluntary demographics (fairness dashboard only)

from __future__ import annotations

import logging
import os
import sys
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ai.nlp import ResumeParser  # noqa: E402

from app import models, schemas  # noqa: E402
from app.database import get_db  # noqa: E402
from app.dependencies import get_current_user  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])

resume_parser = ResumeParser()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_rag_pipeline():
    try:
        from ai.rag import RAGPipeline

        return RAGPipeline()
    except Exception:
        logger.exception("RAG pipeline initialisation failed.")
        return None


# ----------------------------------------------------------------- profile
@router.get("/", response_model=schemas.ProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return current_user


@router.put("/", response_model=schemas.ProfileResponse)
def update_profile(
    profile_update: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # update own profile
    update_data = profile_update.dict(exclude_unset=True)
    if current_user.role == "applicant":
        update_data.pop("company_name", None)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


# ------------------------------------------------------------------ resume
@router.get("/resume", response_model=dict)
def get_resume_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # parsed CV from latest application
    if current_user.role != "applicant":
        raise HTTPException(status_code=403, detail="Only applicants can view resume data")

    application = (
        db.query(models.Application)
        .filter(
            models.Application.user_id == current_user.id,
            models.Application.applicant_id.isnot(None),
        )
        .order_by(models.Application.created_at.desc())
        .first()
    )
    if not application:
        return {
            "message": "No resume data found",
            "extracted_data": None,
            "parsed_resume": None,
        }

    applicant = db.query(models.Applicant).filter(
        models.Applicant.id == application.applicant_id
    ).first()
    if not applicant:
        return {
            "message": "No resume data found",
            "extracted_data": None,
            "parsed_resume": None,
        }

    parsed = {
        "name": f"{applicant.first_name} {applicant.last_name}",
        "first_name": applicant.first_name,
        "last_name": applicant.last_name,
        "email": applicant.email,
        "phone": applicant.phone,
        "skills": applicant.skills or [],
        "experience_years": applicant.experience_years or 0.0,
        "education": applicant.education or [],
        "work_experience": applicant.work_experience or [],
        "resume_text": applicant.resume_text or "",
        "ai_summary": applicant.ai_summary,
        "interview_questions": applicant.interview_questions or [],
        "file_path": applicant.resume_file_path,
        "resume_file_type": applicant.resume_file_type,
    }
    return {
        "message": "Resume data retrieved successfully",
        "file_path": applicant.resume_file_path,
        "extracted_data": parsed,
        "parsed_resume": parsed,
    }


@router.post("/resume", response_model=dict)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # upload resume to profile - applicant only
    if current_user.role != "applicant":
        raise HTTPException(status_code=403, detail="Only applicants can upload resumes")

    file_content = await file.read()
    file_ext = (file.filename or "").rsplit(".", 1)[-1].lower() or "pdf"
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"profile_{current_user.id}_{file_id}.{file_ext}")
    with open(file_path, "wb") as fh:
        fh.write(file_content)

    try:
        parsed = resume_parser.parse_file(file_content, file.filename, use_ai=False)
    except Exception as exc:
        logger.exception("Profile résumé parsing failed for %s", file.filename)
        raise HTTPException(status_code=400, detail=f"Error parsing resume: {exc}") from exc

    return {
        "message": "Resume uploaded successfully",
        "file_path": file_path,
        "extracted_data": {
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years", 0.0),
            "education": parsed.get("education", []),
            "work_experience": parsed.get("work_experience", []),
            "resume_text": parsed.get("resume_text", ""),
        },
    }


@router.post("/resume/generate-summary", response_model=dict)
def generate_resume_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # RAG summary against latest application - applicant only
    if current_user.role != "applicant":
        raise HTTPException(status_code=403, detail="Only applicants can generate resume summaries")

    application = (
        db.query(models.Application)
        .filter(
            models.Application.user_id == current_user.id,
            models.Application.applicant_id.isnot(None),
        )
        .order_by(models.Application.created_at.desc())
        .first()
    )
    if not application or not application.applicant_id:
        raise HTTPException(
            status_code=404,
            detail="No résumé found. Please apply to a job with a CV first.",
        )

    applicant = db.query(models.Applicant).filter(
        models.Applicant.id == application.applicant_id
    ).first()
    if not applicant or not applicant.resume_text:
        raise HTTPException(status_code=404, detail="Résumé text not available.")

    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    rag_pipeline = _get_rag_pipeline()
    if not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="AI features are not available. OPENAI_API_KEY is not configured.",
        )

    try:
        summary_data = rag_pipeline.generate_summary(
            resume_text=applicant.resume_text or "",
            job_description=job.description or "",
        )
    except Exception as exc:
        logger.exception("Summary generation failed for applicant %s", applicant.id)
        raise HTTPException(status_code=500, detail=f"Error generating AI summary: {exc}") from exc

    summary_text = (summary_data or {}).get("summary") or ""
    error_detail = (summary_data or {}).get("error") or ""
    if summary_text and not summary_text.lower().startswith("unable to generate"):
        applicant.ai_summary = summary_text
        return_summary = summary_text
    else:
        applicant.ai_summary = None
        return_summary = None

    try:
        questions = rag_pipeline.generate_interview_questions(
            resume_text=applicant.resume_text or "",
            job_description=job.description,
            num_questions=5,
        )
        if questions and isinstance(questions, list) and questions:
            applicant.interview_questions = (
                questions
                if not (isinstance(questions[0], str) and "Unable to generate" in questions[0])
                else None
            )
        else:
            applicant.interview_questions = None
    except Exception:
        logger.exception("Interview question generation failed (non-fatal).")
        applicant.interview_questions = None

    db.commit()
    db.refresh(applicant)

    return {
        "message": (
            "AI summary generated successfully" if return_summary
            else (error_detail or "AI summary generation failed")
        ),
        "summary": return_summary,
        "strengths": (summary_data or {}).get("strengths", []),
        "weaknesses": (summary_data or {}).get("weaknesses", []),
        "recommendations": (summary_data or {}).get("recommendations", []),
        "interview_questions": applicant.interview_questions or [],
        "error": error_detail or None,
    }


# ----------------------------------------------------------------- delete
@router.delete("/", response_model=dict)
def delete_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # deactivate account (soft delete)
    current_user.is_active = False
    db.commit()
    return {"message": "Profile deactivated successfully"}


# ----------------------------------------------------------- demographics
@router.get("/demographics", response_model=schemas.DemographicResponse)
def get_demographics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return schemas.DemographicResponse(
        consent=bool(current_user.demographic_consent),
        gender=current_user.demographic_gender,
        age_band=current_user.demographic_age_band,
        ethnicity=current_user.demographic_ethnicity,
        disability=current_user.demographic_disability,
    )


@router.put("/demographics", response_model=schemas.DemographicResponse)
def update_demographics(
    payload: schemas.DemographicUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # opt-in demographics for MSD/DIR fairness audit only
    current_user.demographic_consent = bool(payload.consent)
    if payload.consent:
        current_user.demographic_gender = payload.gender
        current_user.demographic_age_band = payload.age_band
        current_user.demographic_ethnicity = payload.ethnicity
        current_user.demographic_disability = payload.disability
    else:
        current_user.demographic_gender = None
        current_user.demographic_age_band = None
        current_user.demographic_ethnicity = None
        current_user.demographic_disability = None
    db.commit()
    db.refresh(current_user)
    return schemas.DemographicResponse(
        consent=bool(current_user.demographic_consent),
        gender=current_user.demographic_gender,
        age_band=current_user.demographic_age_band,
        ethnicity=current_user.demographic_ethnicity,
        disability=current_user.demographic_disability,
    )
