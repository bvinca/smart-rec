# application lifecycle - apply, list, update, interview prep
# apply flow: parse CV sync, create Application with ai_status=queued,
# then background task runs scoring, RAG, XAI, audit logging

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ai.nlp import ResumeParser  # noqa: E402

from app import models, schemas  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import get_db  # noqa: E402
from app.dependencies import get_current_user, require_applicant, require_recruiter  # noqa: E402
from app.services.ai_processor import process_application_ai  # noqa: E402
from app.utils.file_helpers import FileHelper, read_upload_capped  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])

resume_parser = ResumeParser()
file_helper = FileHelper()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# helpers
def _compute_timeline_check(applicant: models.Applicant) -> dict:
    # date-sanity check on stored fields - computed live, not persisted
    # non-fatal if it blows up; don't break the recruiter view
    try:
        from ai.nlp.timeline_validator import validate_timeline
        return validate_timeline({
            "experience_years": applicant.experience_years or 0.0,
            "education": applicant.education or [],
            "work_experience": applicant.work_experience or [],
        })
    except Exception:
        logger.exception("Timeline validation failed for applicant %s", applicant.id)
        return {"warnings": []}


def _serialise_applicant(applicant: models.Applicant) -> dict:
    return {
        "id": applicant.id,
        "first_name": applicant.first_name,
        "last_name": applicant.last_name,
        "email": applicant.email,
        "phone": applicant.phone,
        "skills": applicant.skills or [],
        "experience_years": applicant.experience_years or 0.0,
        "education": applicant.education or [],
        "work_experience": applicant.work_experience or [],
        "match_score": applicant.match_score or 0.0,
        "skill_score": applicant.skill_score or 0.0,
        "experience_score": applicant.experience_score or 0.0,
        "education_score": applicant.education_score or 0.0,
        "overall_score": applicant.overall_score or 0.0,
        "ai_summary": applicant.ai_summary,
        "ai_feedback": applicant.ai_feedback,
        "interview_questions": applicant.interview_questions or [],
        "resume_text": applicant.resume_text,
        "resume_file_path": applicant.resume_file_path,
        "resume_file_type": applicant.resume_file_type,
        "timeline_check": _compute_timeline_check(applicant),
    }


def _serialise_application(
    db: Session,
    application: models.Application,
    job: Optional[models.Job] = None,
) -> dict:
    job = job or db.query(models.Job).filter(models.Job.id == application.job_id).first()
    payload: dict = {
        "id": application.id,
        "user_id": application.user_id,
        "job_id": application.job_id,
        "applicant_id": application.applicant_id,
        "status": application.status,
        "notes": application.notes,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
        "job": job,
        "applicant": None,
        "match_score": None,
        "ai_status": application.ai_status,
        "ai_processed_at": application.ai_processed_at,
        "ai_error": application.ai_error,
    }
    if application.applicant_id:
        applicant = db.query(models.Applicant).filter(
            models.Applicant.id == application.applicant_id
        ).first()
        if applicant:
            payload["applicant"] = _serialise_applicant(applicant)
            payload["match_score"] = applicant.overall_score or 0.0
    else:
        user = db.query(models.User).filter(models.User.id == application.user_id).first()
        if user:
            payload["user"] = {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": None,
            }
    return payload


# apply
@router.post("/apply/{job_id}", response_model=schemas.ApplicationResponse)
async def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_applicant),
):
    # apply to a job - AI runs async, poll until ai_status is ready
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "active":
        raise HTTPException(status_code=400, detail="Job is not accepting applications")

    if (
        db.query(models.Application)
        .filter(
            models.Application.user_id == current_user.id,
            models.Application.job_id == job_id,
        )
        .first()
    ):
        raise HTTPException(status_code=400, detail="You have already applied to this job")

    applicant_id: Optional[int] = None
    ai_status = "skipped"

    if file:
        applicant_id = await _ingest_resume(
            db=db, current_user=current_user, job=job, file=file
        )
        ai_status = "queued" if applicant_id else "skipped"

    application = models.Application(
        user_id=current_user.id,
        job_id=job_id,
        applicant_id=applicant_id,
        status="pending",
        ai_status=ai_status,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    if ai_status == "queued":
        background_tasks.add_task(process_application_ai, application.id)
        logger.info(
            "Application %s queued for AI processing (applicant=%s, job=%s)",
            application.id, applicant_id, job_id,
        )

    return _serialise_application(db, application, job=job)


async def _ingest_resume(
    *,
    db: Session,
    current_user: models.User,
    job: models.Job,
    file: UploadFile,
) -> Optional[int]:
    # parse resume sync and create the Applicant row
    if not file_helper.validate_file_type(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Supported: PDF, DOCX, TXT.",
        )

    file_content = await read_upload_capped(file, settings.MAX_UPLOAD_BYTES)
    if not file_content:
        return None

    if not file_helper.validate_file_content(file_content, file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail="File content does not match its extension or is not a supported document.",
        )

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
        job_id=job.id,
        first_name=parsed.get("first_name") or current_user.first_name or "Unknown",
        last_name=parsed.get("last_name") or current_user.last_name or "",
        email=parsed.get("email") or current_user.email,
        phone=parsed.get("phone"),
        resume_text=parsed.get("resume_text", ""),
        resume_file_path=file_path,
        resume_file_type=file_ext,
        skills=parsed.get("skills", []),
        experience_years=parsed.get("experience_years", 0.0),
        education=parsed.get("education", []),
        work_experience=parsed.get("work_experience", []),
    )
    db.add(applicant)
    db.flush()
    return applicant.id


# list
@router.get("/", response_model=List[schemas.ApplicationResponse])
def get_applications(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # list apps - scope depends on role
    base = db.query(models.Application).options(joinedload(models.Application.job))
    if current_user.role == "applicant":
        base = base.filter(models.Application.user_id == current_user.id)
    else:
        base = base.join(models.Job).filter(models.Job.recruiter_id == current_user.id)

    applications = (
        base.order_by(models.Application.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_serialise_application(db, app, job=app.job) for app in applications]


# get one
@router.get("/{application_id}", response_model=schemas.ApplicationResponse)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # single application by id
    application = db.query(models.Application).filter(
        models.Application.id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if current_user.role == "applicant":
        if application.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
        if not job or job.recruiter_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

    return _serialise_application(db, application)


# update
@router.put("/{application_id}", response_model=schemas.ApplicationResponse)
def update_application(
    application_id: int,
    application_update: schemas.ApplicationUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # recruiter updates status - auto-sends email on hire/reject
    application = db.query(models.Application).filter(
        models.Application.id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    if not job or job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    old_status = application.status
    update_data = application_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)

    new_status = application.status
    if old_status != new_status and new_status in {"hired", "rejected"}:
        background_tasks.add_task(_send_decision_email, application_id, new_status)

    return _serialise_application(db, application, job=job)


def _send_decision_email(application_id: int, status: str) -> None:
    # bg task: generate + send hire/reject email
    from app.database import SessionLocal
    from app.services.email_service import EmailService

    db = SessionLocal()
    try:
        message_type = "hired" if status == "hired" else "rejection"
        service = EmailService()
        try:
            email_result = service.generate_email_for_application(
                application_id=application_id,
                message_type=message_type,
                db=db,
            )
        except Exception:
            logger.exception("Failed to auto-generate %s email for application %s", message_type, application_id)
            return

        email_id = email_result.get("email_id") if isinstance(email_result, dict) else None
        if not email_id:
            logger.warning("Email generation produced no email_id for application %s", application_id)
            return

        try:
            service.send_email(email_id=email_id, db=db)
            logger.info("Auto-sent %s email for application %s", message_type, application_id)
        except Exception:
            logger.exception("Email generated but send failed (application %s).", application_id)
    finally:
        db.close()


# interview prep
_INTERVIEW_PREP_METHOD = "interview_prep_v1"


@router.post(
    "/{application_id}/interview-prep",
    response_model=schemas.InterviewPrepResponse,
)
def get_interview_prep(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_applicant),
):
    # LLM interview prep - cached in ai_audit_logs after first hit
    # 404 not found, 403 wrong user, 400 no applicant row, 503 no OpenAI key
    from datetime import datetime, timezone

    application = (
        db.query(models.Application)
        .filter(models.Application.id == application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not application.applicant_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate interview prep before the CV has been parsed.",
        )

    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    applicant = (
        db.query(models.Applicant)
        .filter(models.Applicant.id == application.applicant_id)
        .first()
    )

    # cache key: applicant + job + scoring_method=interview_prep_v1
    cached_log = (
        db.query(models.AIAuditLog)
        .filter(
            models.AIAuditLog.applicant_id == application.applicant_id,
            models.AIAuditLog.job_id == application.job_id,
            models.AIAuditLog.scoring_method == _INTERVIEW_PREP_METHOD,
        )
        .order_by(models.AIAuditLog.created_at.desc())
        .first()
    )
    if cached_log and isinstance(cached_log.explanation_json, dict):
        payload = cached_log.explanation_json
        return schemas.InterviewPrepResponse(
            application_id=application_id,
            company_overview=payload.get("company_overview", ""),
            position_questions=payload.get("position_questions", []),
            preparation_tips=payload.get("preparation_tips", []),
            cached=True,
            generated_at=cached_log.created_at or datetime.now(timezone.utc),
        )

    # no cache - generate fresh
    try:
        from ai.llm.interview_prep_generator import generate_interview_prep
    except Exception as exc:  # pragma: no cover - import guards
        logger.exception("Interview-prep generator failed to import.")
        raise HTTPException(
            status_code=503,
            detail=f"Interview prep is not available: {exc}",
        ) from exc

    company_name: Optional[str] = None
    if job.recruiter_id:
        recruiter = (
            db.query(models.User)
            .filter(models.User.id == job.recruiter_id)
            .first()
        )
        company_name = recruiter.company_name if recruiter else None

    applicant_skills: List[str] = []
    if applicant and applicant.skills:
        # skills column is JSON - handle list of str or dict
        if isinstance(applicant.skills, list):
            for entry in applicant.skills:
                if isinstance(entry, str):
                    applicant_skills.append(entry)
                elif isinstance(entry, dict) and entry.get("name"):
                    applicant_skills.append(str(entry["name"]))

    try:
        result = generate_interview_prep(
            job_title=job.title or "",
            job_description=job.description or "",
            company_name=company_name,
            applicant_skills=applicant_skills or None,
        )
    except ValueError as exc:
        # missing key or bad LLM response -> 503
        logger.warning("Interview-prep generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Interview prep is currently unavailable: {exc}",
        ) from exc

    # stash in ai_audit_logs - overall_score=0.0 is a placeholder, not a real score
    audit = models.AIAuditLog(
        applicant_id=application.applicant_id,
        job_id=application.job_id,
        overall_score=0.0,
        explanation_json=result,
        scoring_method=_INTERVIEW_PREP_METHOD,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return schemas.InterviewPrepResponse(
        application_id=application_id,
        company_overview=result["company_overview"],
        position_questions=result["position_questions"],
        preparation_tips=result["preparation_tips"],
        cached=False,
        generated_at=audit.created_at or datetime.now(timezone.utc),
    )
