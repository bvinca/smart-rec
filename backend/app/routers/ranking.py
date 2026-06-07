# candidate ranking by Sentence-BERT / OpenAI semantic similarity
from __future__ import annotations

import os
import sys
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from ai import utils as ai_utils
from ai.embeddings import EmbeddingVectorizer, SimilarityCalculator
from app import models, schemas
from app.database import get_db
from app.dependencies import require_recruiter
from app.rate_limit import AI_LIMIT, limiter

router = APIRouter(prefix="/ranking", tags=["ranking"])

# lazy-load so we don't hit OpenAI on import
_vectorizer = None

def get_vectorizer():
    # lazy EmbeddingVectorizer
    global _vectorizer
    if _vectorizer is None:
        _vectorizer = EmbeddingVectorizer()
    return _vectorizer


@router.get("/job/{job_id}", response_model=List[schemas.RankedCandidateResponse])
@limiter.limit(AI_LIMIT)
def rank_candidates_for_job(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # rank applicants for a job by semantic match score
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.recruiter_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    applicants = db.query(models.Applicant).filter(
        models.Applicant.job_id == job_id
    ).all()
    
    if not applicants:
        return []
    
    vectorizer = get_vectorizer()
    job_text = f"{job.title}\n{job.description}\n{job.requirements or ''}"
    job_embedding = vectorizer.generate_embedding(job_text)
    
    ranked_candidates = []
    
    for applicant in applicants:
        embedding_record = db.query(models.Embedding).filter(
            models.Embedding.applicant_id == applicant.id,
            models.Embedding.job_id == job_id
        ).first()
        
        if embedding_record and embedding_record.embedding_vector:
            resume_embedding = embedding_record.embedding_vector
        else:
            resume_text = applicant.resume_text or ""
            if resume_text:
                resume_embedding = vectorizer.generate_embedding(resume_text)
                if not embedding_record:
                    embedding_record = models.Embedding(
                        applicant_id=applicant.id,
                        job_id=job_id,
                        embedding_vector=resume_embedding
                    )
                    db.add(embedding_record)
                else:
                    embedding_record.embedding_vector = resume_embedding
            else:
                resume_embedding = None
        
        if resume_embedding:
            match_score = SimilarityCalculator.calculate_match_score(
                resume_embedding,
                job_embedding
            )
        else:
            match_score = applicant.overall_score or 0.0
        
        ranked_candidates.append({
            "applicant_id": applicant.id,
            "name": f"{applicant.first_name} {applicant.last_name}",
            "email": applicant.email,
            "match_score": match_score,
            "overall_score": applicant.overall_score or 0.0,
            "skills": applicant.skills or [],
            "experience_years": applicant.experience_years or 0.0,
            "ai_summary": applicant.ai_summary,
            "status": applicant.status
        })
    
    # normalize per job when scores actually differ
    match_scores = [c["match_score"] for c in ranked_candidates]
    if match_scores and len(set(match_scores)) > 1:
        normalized_scores = ai_utils.normalize_scores(match_scores)
        for candidate, normalized_score in zip(ranked_candidates, normalized_scores):
            candidate["normalized_score"] = normalized_score
    else:
        for candidate in ranked_candidates:
            candidate["normalized_score"] = candidate["match_score"]
    
    ranked_candidates.sort(key=lambda x: x["match_score"], reverse=True)
    
    for idx, candidate in enumerate(ranked_candidates, 1):
        candidate["rank"] = idx
    
    db.commit()
    
    return ranked_candidates
