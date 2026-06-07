# NLP package - resume parsing, skill extraction, preprocessing. Lazy imports.
# Lazy imports so loading skill_ontology doesn't pull in PyPDF2 / spaCy / transformers.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .parser import ResumeParser  # noqa: F401
    from .preprocess import TextPreprocessor  # noqa: F401
    from .skill_extraction import SkillExtractor  # noqa: F401

__all__ = ["ResumeParser", "SkillExtractor", "TextPreprocessor"]


def __getattr__(name: str) -> Any:
    if name == "ResumeParser":
        return importlib.import_module(".parser", __name__).ResumeParser
    if name == "SkillExtractor":
        return importlib.import_module(".skill_extraction", __name__).SkillExtractor
    if name == "TextPreprocessor":
        return importlib.import_module(".preprocess", __name__).TextPreprocessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
