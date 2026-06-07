# Shared helpers - prompts, constants, PII redaction.
# Imports stay defensive so the package loads even without transformers or spaCy.

from .helpers import AIHelpers
from .pii import maybe_redact, redact_pii
from .prompts import PromptTemplates
from . import constants as AIConstants  # the existing module is a flat namespace

__all__ = [
    "AIConstants",
    "AIHelpers",
    "PromptTemplates",
    "maybe_redact",
    "redact_pii",
]
