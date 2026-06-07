# Embeddings - Sentence-BERT vectorizer + cosine similarity helpers.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .similarity import SimilarityCalculator  # noqa: F401
    from .vectorizer import EmbeddingVectorizer  # noqa: F401

__all__ = ["EmbeddingVectorizer", "SimilarityCalculator"]


def __getattr__(name: str) -> Any:
    # lazy import so importing the package doesn't drag in sentence-transformers
    if name == "EmbeddingVectorizer":
        return importlib.import_module(".vectorizer", __name__).EmbeddingVectorizer
    if name == "SimilarityCalculator":
        return importlib.import_module(".similarity", __name__).SimilarityCalculator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
