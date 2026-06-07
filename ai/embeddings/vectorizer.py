# Sentence-BERT wrapper - all-MiniLM-L6-v2, 384-dim. This is what scoring and RAG share.
# Backends: sbert (default), openai (text-embedding-3-large), auto (key set -> openai, else sbert).
# Model loads once per process. Empty input -> zero vector so cosine doesn't blow up.

from __future__ import annotations

import logging
import os
import sys
from threading import Lock
from typing import Iterable, List, Optional

# make the FastAPI backend importable when this runs in stand-alone scripts
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings  # type: ignore
except Exception:  # pragma: no cover - script execution
    # standalone fallback - read env vars directly
    class _FallbackSettings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "sbert")
        SBERT_MODEL_NAME = os.getenv(
            "SBERT_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
        )

        def resolved_embedding_backend(self) -> str:
            if self.EMBEDDING_BACKEND != "auto":
                return self.EMBEDDING_BACKEND
            return "openai" if self.OPENAI_API_KEY.strip() else "sbert"

    settings = _FallbackSettings()  # type: ignore

logger = logging.getLogger(__name__)

_OPENAI_DIM = 3072  # text-embedding-3-large
_SBERT_DEFAULT_DIM = 384  # all-MiniLM-L6-v2


class EmbeddingVectorizer:
    # SBERT (default) or OpenAI embeddings behind a single API

    _sbert_model = None
    _sbert_lock = Lock()

    def __init__(self, backend: Optional[str] = None) -> None:
        self.backend = (backend or settings.resolved_embedding_backend()).lower()
        if self.backend not in {"sbert", "openai"}:
            raise ValueError(
                f"Unsupported embedding backend '{self.backend}'. Use 'sbert' or 'openai'."
            )

        if self.backend == "openai":
            if not settings.OPENAI_API_KEY.strip():
                # openai requested but no key - fall back to Sentence-BERT
                logger.warning(
                    "OPENAI back-end requested but OPENAI_API_KEY is empty; "
                    "falling back to local Sentence-BERT."
                )
                self.backend = "sbert"
            else:
                from openai import OpenAI

                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self._openai_model = settings.OPENAI_EMBEDDING_MODEL
                self.embedding_dim = _OPENAI_DIM

        if self.backend == "sbert":
            model = self._get_sbert_model(settings.SBERT_MODEL_NAME)
            self._sbert = model
            self.embedding_dim = (
                model.get_sentence_embedding_dimension() if model else _SBERT_DEFAULT_DIM
            )

    @classmethod
    def _get_sbert_model(cls, model_name: str):
        # lazy + locked so we only ever load the big model once per process
        if cls._sbert_model is not None:
            return cls._sbert_model
        with cls._sbert_lock:
            if cls._sbert_model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    logger.info("Loading Sentence-BERT model %s ...", model_name)
                    cls._sbert_model = SentenceTransformer(model_name)
                except Exception as exc:  # pragma: no cover - depends on env
                    logger.error(
                        "Failed to load Sentence-BERT model '%s': %s. Embeddings will be zero vectors.",
                        model_name,
                        exc,
                    )
                    cls._sbert_model = None
        return cls._sbert_model

    def _zero_vector(self) -> List[float]:
        return [0.0] * self.embedding_dim

    def generate_embedding(self, text: str) -> List[float]:
        # single-text embed; empty input -> zero vector
        if not text or not text.strip():
            return self._zero_vector()
        try:
            if self.backend == "openai":
                response = self._openai_client.embeddings.create(
                    model=self._openai_model,
                    input=text[:8000],
                )
                return list(response.data[0].embedding)

            if self._sbert is None:
                return self._zero_vector()
            vector = self._sbert.encode(
                [text], convert_to_numpy=True, normalize_embeddings=True
            )[0]
            return [float(x) for x in vector]
        except Exception as exc:  # pragma: no cover - network errors
            logger.exception("Embedding generation failed: %s", exc)
            return self._zero_vector()

    def generate_embeddings_batch(self, texts: Iterable[str]) -> List[List[float]]:
        # batch embed - one model/network call when possible
        cleaned = [t if (t and t.strip()) else " " for t in texts]
        if not cleaned:
            return []

        try:
            if self.backend == "openai":
                response = self._openai_client.embeddings.create(
                    model=self._openai_model,
                    input=cleaned,
                )
                return [list(item.embedding) for item in response.data]

            if self._sbert is None:
                return [self._zero_vector() for _ in cleaned]
            vectors = self._sbert.encode(
                cleaned, convert_to_numpy=True, normalize_embeddings=True
            )
            return [[float(x) for x in vec] for vec in vectors]
        except Exception as exc:  # pragma: no cover - network errors
            logger.exception("Batch embedding failed: %s", exc)
            return [self._zero_vector() for _ in cleaned]
