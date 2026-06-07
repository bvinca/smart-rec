# background AI processor - fires after an application is submitted.
# four jobs in one entry point:
#   1. scoring     - ScoringService → Applicant row
#   2. RAG         - summary + interview Qs when an OpenAI key is set
#   3. XAI         - XAIExplainer → narrative + attributions
#   4. audit       - every (score, explanation) pair → ai_audit_logs
#
# runs inside FastAPI BackgroundTasks. opens its own SQLAlchemy session
# because the request-scoped one is closed by the time the task fires.

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app import models
from app.services.embedding_cache import EmbeddingCache
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)


_DEFAULT_QUESTIONS = {
    "Tell me about your experience with the technologies mentioned in this role.",
    "Describe a challenging project you worked on and how you solved it.",
    "How do you stay updated with industry trends?",
    "What motivates you in your career?",
    "Why are you interested in this position?",
}


def process_application_ai(application_id: int) -> None:
    # score + summarise + explain, in the background
    db: Session = SessionLocal()
    try:
        application = db.query(models.Application).filter(
            models.Application.id == application_id
        ).first()
        if not application:
            logger.warning("AI processor: application %s not found", application_id)
            return
        if not application.applicant_id:
            application.ai_status = "skipped"
            application.ai_processed_at = datetime.utcnow()
            db.commit()
            return

        applicant = db.query(models.Applicant).filter(
            models.Applicant.id == application.applicant_id
        ).first()
        job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
        if not applicant or not job:
            logger.warning(
                "AI processor: missing applicant=%s or job=%s for application=%s",
                application.applicant_id, application.job_id, application_id,
            )
            return

        application.ai_status = "processing"
        db.commit()

        try:
            _score_and_explain(db, application=application, applicant=applicant, job=job)
            _generate_rag_artifacts(db, applicant=applicant, job=job)
        except Exception as exc:
            logger.exception("AI processor failed for application %s", application_id)
            application.ai_status = "failed"
            application.ai_error = str(exc)[:1000]
            application.ai_processed_at = datetime.utcnow()
            db.commit()
            return

        application.ai_status = "ready"
        application.ai_processed_at = datetime.utcnow()
        application.ai_error = None
        db.commit()
    finally:
        db.close()


# scoring
def _score_and_explain(
    db: Session,
    *,
    application: models.Application,
    applicant: models.Applicant,
    job: models.Job,
) -> None:
    # scorer + XAI, persisted onto the Applicant row
    scoring_service = ScoringService(db=db)
    result = scoring_service.calculate_scores(
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
        required_education_level=getattr(job, "required_education_level", None),
        required_skills_override=getattr(job, "required_skills", None),
    )

    # cache the embedding under whichever backend produced it
    try:
        cache = EmbeddingCache(db, model_name=settings.resolved_embedding_backend())
        cache.put(
            text=applicant.resume_text or "",
            vector=result.get("resume_embedding") or [],
            applicant_id=applicant.id,
            job_id=job.id,
        )
    except Exception:
        logger.exception("Failed to cache résumé embedding (non-fatal).")

    applicant.match_score = result["match_score"]
    applicant.skill_score = result["skill_score"]
    applicant.experience_score = result["experience_score"]
    applicant.education_score = result["education_score"]
    applicant.overall_score = result["overall_score"]

    explanation_payload = _explain(applicant=applicant, job=job, scoring_result=result)
    _audit(
        db,
        applicant=applicant,
        job=job,
        scoring_result=result,
        explanation=explanation_payload,
    )

    # always generate questions deterministically - that way every candidate
    # has them even with no OpenAI key. the RAG path can overwrite below
    # when a key is available.
    _generate_deterministic_questions(applicant=applicant, job=job, scoring_result=result)

    db.commit()


def _generate_deterministic_questions(
    *,
    applicant: models.Applicant,
    job: models.Job,
    scoring_result: Dict[str, Any],
) -> None:
    # template-driven question generator. runs unconditionally so the
    # no-LLM eval config still surfaces tailored questions (matched +
    # missing skills, recent role, timeline warnings).
    try:
        from ai.llm.question_generator import QuestionGenerator
        from ai.nlp.timeline_validator import validate_timeline

        timeline = validate_timeline({
            "experience_years": applicant.experience_years or 0.0,
            "education": applicant.education or [],
            "work_experience": applicant.work_experience or [],
        })
        questions = QuestionGenerator().generate_deterministic_questions(
            parsed_data={
                "resume_text": applicant.resume_text or "",
                "skills": applicant.skills or [],
                "experience_years": applicant.experience_years or 0.0,
                "education": applicant.education or [],
                "work_experience": applicant.work_experience or [],
            },
            job_title=job.title,
            job_description=job.description,
            matched_skills=scoring_result.get("matched_skills"),
            missing_skills=scoring_result.get("missing_skills"),
            timeline_warnings=(timeline or {}).get("warnings"),
            num_questions=6,
        )
        if questions:
            applicant.interview_questions = questions
    except Exception:  # pragma: no cover - non-fatal
        logger.exception("Deterministic question generation failed.")


def _explain(
    *,
    applicant: models.Applicant,
    job: models.Job,
    scoring_result: Dict[str, Any],
) -> Dict[str, Any]:
    # XAI explainer wrapper - returns {} on failure
    try:
        from ai.explanation.xai_explainer import XAIExplainer

        explainer = XAIExplainer()
        scores = {
            "skill_score": scoring_result["skill_score"],
            "experience_score": scoring_result["experience_score"],
            "education_score": scoring_result["education_score"],
            "match_score": scoring_result["match_score"],
            "overall_score": scoring_result["overall_score"],
        }
        return explainer.explain_scoring(
            resume_text=applicant.resume_text or "",
            job_description=job.description or "",
            scores=scores,
            candidate_skills=applicant.skills or [],
            candidate_experience_years=applicant.experience_years or 0.0,
            weights=scoring_result.get("weights_used"),
            matched_skills=scoring_result.get("matched_skills"),
            missing_skills=scoring_result.get("missing_skills"),
        )
    except Exception:
        logger.exception("XAI explanation failed (non-fatal).")
        return {}


# audit log
def _audit(
    db: Session,
    *,
    applicant: models.Applicant,
    job: models.Job,
    scoring_result: Dict[str, Any],
    explanation: Dict[str, Any],
) -> None:
    # one ai_audit_logs row per scoring run
    try:
        narrative = explanation.get("overall_summary") or scoring_result.get("explanation", {}).get(
            "overall_assessment", ""
        )
        log = models.AIAuditLog(
            applicant_id=applicant.id,
            job_id=job.id,
            overall_score=scoring_result["overall_score"],
            skill_score=scoring_result["skill_score"],
            experience_score=scoring_result["experience_score"],
            education_score=scoring_result["education_score"],
            match_score=scoring_result["match_score"],
            explanation=narrative or None,
            explanation_json={
                "feature_attributions": explanation.get("feature_attributions"),
                "counterfactuals": explanation.get("counterfactuals"),
                "matched_skills": explanation.get("matched_skills") or scoring_result.get("matched_skills"),
                "missing_skills": explanation.get("missing_skills") or scoring_result.get("missing_skills"),
                "weights_used": scoring_result.get("weights_used"),
                "score_breakdown": scoring_result.get("score_breakdown"),
            },
            scoring_method=(scoring_result.get("score_breakdown", {}) or {}).get(
                "scoring_method", "hybrid"
            ),
            llm_available=bool(explanation.get("llm_available")),
        )
        db.add(log)
    except Exception:
        logger.exception("Failed to write AI audit log (non-fatal).")


# RAG
def _generate_rag_artifacts(
    db: Session,
    *,
    applicant: models.Applicant,
    job: models.Job,
) -> None:
    # summary + feedback + interview Qs via the RAG pipeline (if a key is set)
    try:
        from ai.rag.rag_pipeline import RAGPipeline

        if not (settings.OPENAI_API_KEY or "").strip():
            logger.debug("RAG generation skipped: no OPENAI_API_KEY configured.")
            return

        pipeline = RAGPipeline()
    except Exception:
        logger.exception("RAG pipeline unavailable.")
        return

    # summary
    try:
        summary_data = pipeline.generate_summary(
            resume_text=applicant.resume_text or "",
            job_description=job.description or "",
        )
        summary_text = (summary_data or {}).get("summary") or ""
        if summary_text and not summary_text.lower().startswith("unable to generate"):
            applicant.ai_summary = summary_text
        else:
            applicant.ai_summary = None
    except Exception:
        logger.exception("RAG summary generation failed (non-fatal).")

    # feedback
    try:
        feedback_text = pipeline.generate_feedback(
            resume_text=applicant.resume_text or "",
            job_description=job.description or "",
            scores={
                "match_score": applicant.match_score or 0.0,
                "skill_score": applicant.skill_score or 0.0,
                "experience_score": applicant.experience_score or 0.0,
            },
        )
        if feedback_text and not feedback_text.lower().startswith("unable to generate"):
            applicant.ai_feedback = feedback_text
    except Exception:
        logger.exception("RAG feedback generation failed (non-fatal).")

    # interview questions
    try:
        questions = pipeline.generate_interview_questions(
            resume_text=applicant.resume_text or "",
            job_description=job.description or "",
            num_questions=5,
        )
        questions = _filter_default_questions(questions)
        if questions:
            applicant.interview_questions = questions
    except Exception:
        logger.exception("RAG question generation failed (non-fatal).")

    db.commit()


def _filter_default_questions(questions: Optional[List[str]]) -> List[str]:
    if not questions:
        return []
    if questions and questions[0] in _DEFAULT_QUESTIONS:
        return []
    return [q for q in questions if q]
