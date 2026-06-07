# PII redaction - strip identifiers before CV text goes to an external LLM.
# Blind screening depends on this. Regex is intentionally aggressive - over-redact beats a leak.
# Catches: emails -> [EMAIL], phones -> [PHONE], urls -> [URL],
# addresses -> [ADDRESS], postcodes -> [POSTCODE], known names -> [NAME].
# Optional spaCy pass also masks PERSON / GPE entities if the model is installed.

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_PHONE_PATTERNS = [
    re.compile(r"\+?\d{1,3}[\s\-.()]*\(?\d{2,4}\)?[\s\-.()]*\d{3,4}[\s\-.]*\d{3,4}"),
    re.compile(r"\(\d{3}\)\s?\d{3}[-. ]\d{4}"),
]
_ADDRESS_HINTS = re.compile(
    r"\b\d{1,5}[A-Za-z]?\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+"
    r"(Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|Way|Square|Sq\.?)",
    re.IGNORECASE,
)
_POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b")


def redact_pii(
    text: str,
    candidate_names: Optional[Iterable[str]] = None,
) -> str:
    # mask out personal data. candidate_names = name fragments the caller already
    # knows belong to the candidate (first/last/full) -> replaced with [NAME].
    if not text:
        return text

    redacted = _EMAIL_RE.sub("[EMAIL]", text)
    redacted = _URL_RE.sub("[URL]", redacted)
    for pattern in _PHONE_PATTERNS:
        redacted = pattern.sub("[PHONE]", redacted)
    redacted = _ADDRESS_HINTS.sub("[ADDRESS]", redacted)
    redacted = _POSTCODE_RE.sub("[POSTCODE]", redacted)

    if candidate_names:
        for name in candidate_names:
            name = (name or "").strip()
            if not name:
                continue
            try:
                redacted = re.sub(rf"\b{re.escape(name)}\b", "[NAME]", redacted, flags=re.IGNORECASE)
            except re.error:  # pragma: no cover - regex compile fail
                continue

    # optional spaCy pass for PERSON / GPE - only if the model is installed
    try:
        import spacy  # type: ignore

        global _NLP  # noqa: PLW0603 - module-level cache
        if "_NLP" not in globals():
            try:
                _NLP = spacy.load("en_core_web_sm")
            except Exception:  # pragma: no cover - model not present
                _NLP = None
        if _NLP is not None:
            doc = _NLP(redacted[:5000])
            person_spans = [(ent.start_char, ent.end_char) for ent in doc.ents if ent.label_ == "PERSON"]
            for start, end in reversed(person_spans):
                redacted = redacted[:start] + "[NAME]" + redacted[end:]
    except Exception:  # pragma: no cover - spaCy not installed
        pass

    return redacted


def maybe_redact(text: str, enabled: bool, candidate_names: Optional[Iterable[str]] = None) -> str:
    # thin wrapper for callers that read the feature flag from settings
    return redact_pii(text, candidate_names=candidate_names) if enabled else text
