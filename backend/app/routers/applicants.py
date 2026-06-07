# applicant routes - CV upload, scoring, RAG summary, download

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ai.nlp import ResumeParser  # noqa: E402

from app import models, schemas  # noqa: E402
from app.database import get_db  # noqa: E402
from app.dependencies import get_current_user, require_recruiter  # noqa: E402
from app.services.ai_processor import process_application_ai  # noqa: E402
from app.services.scoring_service import ScoringService  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applicants", tags=["applicants"])

resume_parser = ResumeParser()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

_DEFAULT_QUESTIONS = {
    "Tell me about your experience with the technologies mentioned in this role.",
    "Describe a challenging project you worked on and how you solved it.",
    "How do you stay updated with industry trends?",
    "What motivates you in your career?",
    "Why are you interested in this position?",
}


def _get_rag_pipeline():
    # lazy RAG import - OpenAI optional
    try:
        from ai.rag import RAGPipeline

        return RAGPipeline()
    except Exception:
        logger.exception("RAG pipeline initialisation failed.")
        return None


# ---------------------------------------------------------------- upload
@router.post("/upload", response_model=schemas.UploadResponse)
async def upload_cv(
    job_id: int,
    file: UploadFile = File(...),
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # recruiter-side CV upload + parse
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    file_content = await file.read()
    file_ext = (file.filename or "").rsplit(".", 1)[-1].lower() or "pdf"
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{file_ext}")
    with open(file_path, "wb") as fh:
        fh.write(file_content)

    try:
        parsed = resume_parser.parse_file(file_content, file.filename, use_ai=False)
    except Exception as exc:
        logger.exception("Résumé parsing failed for %s", file.filename)
        raise HTTPException(status_code=400, detail=f"Error parsing resume: {exc}") from exc

    applicant = models.Applicant(
        job_id=job_id,
        first_name=parsed.get("first_name") or first_name or "Unknown",
        last_name=parsed.get("last_name") or last_name or "",
        email=parsed.get("email") or email or f"{file_id}@example.com",
        phone=parsed.get("phone") or phone,
        resume_text=parsed.get("resume_text", ""),
        resume_file_path=file_path,
        resume_file_type=file_ext,
        skills=parsed.get("skills", []),
        experience_years=parsed.get("experience_years", 0.0),
        education=parsed.get("education", []),
        work_experience=parsed.get("work_experience", []),
    )
    db.add(applicant)
    db.commit()
    db.refresh(applicant)

    return {
        "applicant_id": applicant.id,
        "message": "Resume uploaded and parsed successfully",
        "extracted_data": {
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years", 0.0),
            "education": parsed.get("education", []),
            "work_experience": parsed.get("work_experience", []),
        },
    }


# ------------------------------------------------------------------ list
@router.get("/", response_model=List[schemas.Applicant])
def get_applicants(
    job_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # list applicants - scoped by role
    if current_user.role == "recruiter":
        query = db.query(models.Applicant).join(models.Job).filter(
            models.Job.recruiter_id == current_user.id
        )
        if job_id:
            job = db.query(models.Job).filter(
                models.Job.id == job_id,
                models.Job.recruiter_id == current_user.id,
            ).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            query = query.filter(models.Applicant.job_id == job_id)
    else:
        # filter by application ownership, not email
        query = (
            db.query(models.Applicant)
            .join(models.Application, models.Application.applicant_id == models.Applicant.id)
            .filter(models.Application.user_id == current_user.id)
        )
        if job_id:
            query = query.filter(models.Applicant.job_id == job_id)

    return (
        query.order_by(models.Applicant.overall_score.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{applicant_id}", response_model=schemas.Applicant)
def get_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # one applicant by id
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")
    if current_user.role == "recruiter":
        job = db.query(models.Job).filter(models.Job.id == applicant.job_id).first()
        if not job or job.recruiter_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    return applicant


# ----------------------------------------------------------------- score
@router.post("/{applicant_id}/score", response_model=schemas.ScoreResponse)
def score_applicant(
    applicant_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # re-score on demand - sync scorer, bg task for RAG/XAI/audit
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    job = db.query(models.Job).filter(models.Job.id == applicant.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    scoring_service = ScoringService(db=db)
    scores = scoring_service.calculate_scores(
        resume_text=applicant.resume_text or "",
        job_description=job.description,
        job_requirements=job.requirements or "",
        applicant_skills=applicant.skills or [],
        applicant_experience_years=applicant.experience_years or 0.0,
        applicant_education=applicant.education or [],
        applicant_work_experience=applicant.work_experience or [],
        recruiter_id=job.recruiter_id,
        job_id=job.id,
        use_adaptive_weights=True,
    )

    applicant.match_score = scores["match_score"]
    applicant.skill_score = scores["skill_score"]
    applicant.experience_score = scores["experience_score"]
    applicant.education_score = scores["education_score"]
    applicant.overall_score = scores["overall_score"]

    db.commit()
    db.refresh(applicant)

    # queue RAG/XAI/audit on the latest application for this applicant
    application = (
        db.query(models.Application)
        .filter(models.Application.applicant_id == applicant.id)
        .order_by(models.Application.created_at.desc())
        .first()
    )
    if application:
        application.ai_status = "queued"
        db.commit()
        background_tasks.add_task(process_application_ai, application.id)

    return {
        "applicant_id": applicant.id,
        "job_id": job.id,
        "match_score": scores["match_score"],
        "skill_score": scores["skill_score"],
        "experience_score": scores["experience_score"],
        "education_score": scores["education_score"],
        "overall_score": scores["overall_score"],
        "explanation": scores["explanation"],
    }


# --------------------------------------------------------------- summary
@router.post("/{applicant_id}/summary", response_model=schemas.SummaryResponse)
def generate_summary(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # RAG summary + feedback + interview Qs - recruiter only
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    job = db.query(models.Job).filter(models.Job.id == applicant.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    rag_pipeline = _get_rag_pipeline()
    if not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="AI features not available. OPENAI_API_KEY not configured.",
        )

    summary_data = rag_pipeline.generate_summary(
        resume_text=applicant.resume_text or "",
        job_description=job.description,
    )
    feedback = rag_pipeline.generate_feedback(
        resume_text=applicant.resume_text or "",
        job_description=job.description,
        scores={
            "match_score": applicant.match_score or 0.0,
            "skill_score": applicant.skill_score or 0.0,
            "experience_score": applicant.experience_score or 0.0,
        },
    )
    questions = rag_pipeline.generate_interview_questions(
        resume_text=applicant.resume_text or "",
        job_description=job.description,
        num_questions=5,
    )

    summary_text = (summary_data or {}).get("summary") or ""
    if summary_text and not summary_text.lower().startswith("unable to generate"):
        applicant.ai_summary = summary_text
    else:
        applicant.ai_summary = None

    if feedback and not feedback.lower().startswith("unable to generate"):
        applicant.ai_feedback = feedback
    else:
        applicant.ai_feedback = None

    if questions and isinstance(questions, list):
        if questions[0] not in _DEFAULT_QUESTIONS:
            applicant.interview_questions = questions
        else:
            applicant.interview_questions = None
    else:
        applicant.interview_questions = None

    db.commit()
    db.refresh(applicant)

    return {
        "applicant_id": applicant.id,
        "summary": summary_data.get("summary", "") if summary_data else "",
        "feedback": feedback or "",
        "strengths": (summary_data or {}).get("strengths", []),
        "weaknesses": (summary_data or {}).get("weaknesses", []),
        "recommendations": (summary_data or {}).get("recommendations", []),
    }


# ---------------------------------------------------- regenerate questions
@router.post("/{applicant_id}/regenerate-questions", response_model=dict)
def regenerate_questions(
    applicant_id: int,
    request: schemas.RegenerateQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # regenerate interview Qs from recruiter feedback
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    job = db.query(models.Job).filter(models.Job.id == applicant.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.recruiter_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only regenerate questions for applicants in your own jobs",
        )

    if not applicant.interview_questions:
        raise HTTPException(
            status_code=400,
            detail="No existing interview questions found. Please generate questions first.",
        )

    rag_pipeline = _get_rag_pipeline()
    if not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="AI features not available. OPENAI_API_KEY not configured.",
        )

    try:
        new_questions = rag_pipeline.regenerate_questions_with_feedback(
            resume_text=applicant.resume_text or "",
            current_questions=applicant.interview_questions,
            feedback=request.feedback,
            job_description=job.description or "",
            num_questions=request.num_questions or 5,
        )
    except Exception as exc:
        logger.exception("regenerate_questions failed for applicant %s", applicant_id)
        raise HTTPException(
            status_code=500, detail=f"Error regenerating questions: {exc}"
        ) from exc

    if (
        not new_questions
        or not isinstance(new_questions, list)
        or new_questions[0] in _DEFAULT_QUESTIONS
    ):
        return {
            "success": False,
            "message": (
                "Regenerated questions appear to be defaults; please check your "
                "OpenAI quota or refine the feedback."
            ),
            "questions": applicant.interview_questions,
        }

    applicant.interview_questions = new_questions
    db.commit()
    db.refresh(applicant)
    logger.info("Regenerated %d questions for applicant %s", len(new_questions), applicant_id)
    return {
        "success": True,
        "message": f"Regenerated {len(new_questions)} interview questions.",
        "questions": new_questions,
    }


# ---------------------------------------------------------------- update
@router.put("/{applicant_id}", response_model=schemas.Applicant)
def update_applicant(
    applicant_id: int,
    applicant_update: schemas.ApplicantUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # update applicant fields - recruiter only
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    job = db.query(models.Job).filter(models.Job.id == applicant.job_id).first()
    if not job or job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = applicant_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(applicant, field, value)

    db.commit()
    db.refresh(applicant)
    return applicant


# -------------------------------------------------------------- download
@router.get("/{applicant_id}/download")
def download_resume(
    applicant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # download resume file - recruiter only
    applicant = db.query(models.Applicant).filter(models.Applicant.id == applicant_id).first()
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found")

    job = db.query(models.Job).filter(models.Job.id == applicant.job_id).first()
    if not job or job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not applicant.resume_file_path or not os.path.exists(applicant.resume_file_path):
        raise HTTPException(status_code=404, detail="Resume file not found")

    media_type = (
        "application/pdf"
        if applicant.resume_file_type == "pdf"
        else "application/msword"
    )
    return FileResponse(
        applicant.resume_file_path,
        media_type=media_type,
        filename=f"{applicant.first_name}_{applicant.last_name}_resume.{applicant.resume_file_type}",
    )
