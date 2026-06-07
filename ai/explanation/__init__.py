# XAI explanation package - lazy import to keep startup light.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .xai_explainer import XAIExplainer  # noqa: F401

__all__ = ["XAIExplainer"]


def __getattr__(name: str) -> Any:
    if name == "XAIExplainer":
        return importlib.import_module(".xai_explainer", __name__).XAIExplainer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
