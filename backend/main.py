# main FastAPI app - logging, CORS, routers, /reports for fairness plots

from __future__ import annotations

import os
import sys

# repo root on sys.path so `ai/` imports work
ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT_PATH not in sys.path:
    sys.path.insert(0, ROOT_PATH)

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import models
from app.config import settings
from app.database import Base, engine
from app.dependencies import require_recruiter
from app.logging_config import configure_logging, get_logger
from app.rate_limit import limiter
from app.routers import (
    analytics,
    applicants,
    applications,
    auth,
    emails,
    enhancement,
    explanation,
    fairness,
    feedback,
    interviews,
    jobs,
    notes,
    profile,
    ranking,
    resume,
    visualization,
)

configure_logging()
logger = get_logger(__name__)

# create_all keeps the eval harness reproducible; prod runs Alembic
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SmartRecruiter API",
    description=(
        "AI-powered Applicant Tracking System combining Sentence-BERT semantic "
        "matching, RAG-based recruiter assistance, fairness auditing (MSD/DIR/SPD) "
        "and explainable AI."
    ),
    version="1.1.0",
)

# rate limiter has to land on app.state before the middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    jobs.router,
    applicants.router,
    applications.router,
    profile.router,
    interviews.router,
    analytics.router,
    resume.router,
    ranking.router,
    enhancement.router,
    fairness.router,
    explanation.router,
    visualization.router,
    emails.router,
    feedback.router,
    notes.router,
):
    app.include_router(router)

# static mount for the fairness plots (heatmaps, bias-reduction charts)
reports_dir = os.path.join(ROOT_PATH, "ai", "reports")
if os.path.exists(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")


@app.on_event("startup")
def _on_startup() -> None:
    backend = settings.resolved_embedding_backend()
    logger.info(
        "SmartRecruiter API ready (debug=%s, embeddings=%s, db=%s)",
        settings.DEBUG,
        backend,
        settings.DATABASE_URL.split("://", 1)[0],
    )

    # warm the embedding model - first user request would otherwise eat
    # the ~3-5 s SBERT load. cheap network call for the OpenAI backend.
    try:
        from ai.embeddings import EmbeddingVectorizer

        vectorizer = EmbeddingVectorizer()
        vectorizer.generate_embedding("warmup")
        logger.info(
            "Embedding model warm (backend=%s, dim=%d).",
            vectorizer.backend, vectorizer.embedding_dim,
        )
    except Exception:  # pragma: no cover - warmup is best-effort
        logger.exception("Embedding warmup failed.")

    # seed the RAG retriever with the static corpus + every active job
    # description so top-3 retrieval has real data to draw from
    try:
        from sqlalchemy.orm import Session

        from ai.rag.retriever import get_retriever
        from app.database import SessionLocal
        from app.models import Job

        retriever = get_retriever()
        if retriever.document_count == 0:
            retriever.bootstrap()

        session: Session = SessionLocal()
        try:
            jobs = session.query(Job).filter(Job.status == "active").all()
            job_docs = [
                {
                    "doc_id": f"job_{j.id}",
                    "title": j.title,
                    "text": (j.description or "") + "\n" + (j.requirements or ""),
                    "source": "job_posting",
                }
                for j in jobs
            ]
            if job_docs:
                added = retriever.add_documents(job_docs)
                logger.info("RAG retriever seeded with %d job postings.", added)
        finally:
            session.close()
    except Exception:  # pragma: no cover - retrieval is best-effort
        logger.exception("RAG retriever bootstrap failed.")


@app.get("/")
def read_root() -> dict:
    return {
        "status": "SmartRecruiter API Running",
        "version": app.version,
        "docs": "/docs",
        "embedding_backend": settings.resolved_embedding_backend(),
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "healthy"}


@app.get("/debug/openai-status")
@limiter.limit("3/minute")
def check_openai_status(
    request: Request,
    current_user: models.User = Depends(require_recruiter),
) -> dict:
    # debug-only OpenAI quota probe. three layers of defence because every
    # call hits the OpenAI API:
    #   1. 404 unless DEBUG=True
    #   2. recruiter auth required
    #   3. rate-limited to 3/min
    # response never echoes the API key
    if not getattr(settings, "DEBUG", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    api_key = settings.OPENAI_API_KEY
    has_key = bool(api_key.strip())

    if not has_key:
        return {
            "api_key_configured": False,
            "embedding_backend": settings.resolved_embedding_backend(),
            "message": "No OpenAI key configured. Local Sentence-BERT path will be used.",
        }

    try:
        from ai.llm.openai_client import OpenAIClient

        client = OpenAIClient()
        client.client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": "Say 'OK'"}],
            max_tokens=5,
        )
        quota_status = "available"
        error = None
    except Exception as exc:  # noqa: BLE001 - surface config errors
        quota_status = "error"
        error = str(exc)

    return {
        "api_key_configured": True,
        "quota_status": quota_status,
        "error": error,
        "embedding_backend": settings.resolved_embedding_backend(),
    }
