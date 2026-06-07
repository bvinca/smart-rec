# LLM package - OpenAI wrappers; lazy attrs avoid pulling in openai at import.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .openai_client import OpenAIClient  # noqa: F401
    from .question_generator import QuestionGenerator  # noqa: F401
    from .summarizer import Summarizer  # noqa: F401

__all__ = ["OpenAIClient", "Summarizer", "QuestionGenerator"]


def __getattr__(name: str) -> Any:
    if name == "OpenAIClient":
        return importlib.import_module(".openai_client", __name__).OpenAIClient
    if name == "Summarizer":
        return importlib.import_module(".summarizer", __name__).Summarizer
    if name == "QuestionGenerator":
        return importlib.import_module(".question_generator", __name__).QuestionGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
