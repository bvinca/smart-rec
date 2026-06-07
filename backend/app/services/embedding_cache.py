# embedding cache in the embeddings table
# skips re-embed on same text - keyed by sha256 + model_name
# swap sbert/openai backend and old vectors don't match anymore

from __future__ import annotations

import hashlib
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)


def text_hash(text: str) -> str:
    # 64-char hex SHA-256 of the trimmed text
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


class EmbeddingCache:
    # simple get/put over embeddings rows

    def __init__(self, db: Session, model_name: str) -> None:
        self.db = db
        self.model_name = model_name

    def get(self, text: str) -> Optional[List[float]]:
        digest = text_hash(text)
        row = (
            self.db.query(models.Embedding)
            .filter(
                models.Embedding.text_hash == digest,
                models.Embedding.model_name == self.model_name,
            )
            .order_by(models.Embedding.created_at.desc())
            .first()
        )
        if row and isinstance(row.embedding_vector, list) and row.embedding_vector:
            return list(row.embedding_vector)
        return None

    def put(
        self,
        text: str,
        vector: List[float],
        applicant_id: Optional[int] = None,
        job_id: Optional[int] = None,
    ) -> None:
        if not vector:
            return
        digest = text_hash(text)
        existing = (
            self.db.query(models.Embedding)
            .filter(
                models.Embedding.text_hash == digest,
                models.Embedding.model_name == self.model_name,
            )
            .first()
        )
        if existing:
            existing.embedding_vector = vector
            if applicant_id is not None:
                existing.applicant_id = applicant_id
            if job_id is not None:
                existing.job_id = job_id
        else:
            self.db.add(
                models.Embedding(
                    applicant_id=applicant_id,
                    job_id=job_id,
                    text_hash=digest,
                    model_name=self.model_name,
                    embedding_vector=vector,
                )
            )
        try:
            self.db.commit()
        except Exception:  # pragma: no cover - rollback for caller safety
            logger.exception("EmbeddingCache.put commit failed; rolling back.")
            self.db.rollback()
