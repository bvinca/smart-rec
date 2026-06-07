# RAG package - retriever, generator, pipeline. Lazy imports.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .generator import RAGGenerator  # noqa: F401
    from .rag_pipeline import RAGPipeline  # noqa: F401
    from .retriever import RAGRetriever  # noqa: F401

__all__ = ["RAGGenerator", "RAGPipeline", "RAGRetriever"]


def __getattr__(name: str) -> Any:
    if name == "RAGRetriever":
        return importlib.import_module(".retriever", __name__).RAGRetriever
    if name == "RAGGenerator":
        return importlib.import_module(".generator", __name__).RAGGenerator
    if name == "RAGPipeline":
        return importlib.import_module(".rag_pipeline", __name__).RAGPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
