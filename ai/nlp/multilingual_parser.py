# Multilingual resume parsing - ResumeParser + langdetect + translation.
# Optional: langdetect (language ID), deep-translator (translate to English).
# Without them, behaves like ResumeParser with detected_language="en".
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "../../../backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# optional: language detection
LANGDETECT_AVAILABLE = False
try:
    from langdetect import DetectorFactory, detect  # type: ignore[import]

    DetectorFactory.seed = 0  # makes detection reproducible
    LANGDETECT_AVAILABLE = True
except ImportError:
    logger.info(
        "langdetect not installed — language detection disabled. "
        "Install with: pip install langdetect"
    )

# optional: translation via deep-translator (googletrans was abandoned)
TRANSLATOR_AVAILABLE = False
_GoogleTranslator = None
try:
    from deep_translator import GoogleTranslator as _GoogleTranslator  # type: ignore[import]

    TRANSLATOR_AVAILABLE = True
except ImportError:
    logger.info(
        "deep-translator not installed — translation disabled. "
        "Install with: pip install deep-translator"
    )

from .parser import ResumeParser


class MultilingualResumeParser(ResumeParser):
    # ResumeParser + optional language detect + translate. Degrades silently to
    # English-only when the optional deps aren't installed.

    def __init__(self) -> None:
        super().__init__()
        self._translator_cls = _GoogleTranslator if TRANSLATOR_AVAILABLE else None
        if TRANSLATOR_AVAILABLE:
            logger.info("MultilingualResumeParser: deep-translator available — translation enabled.")
        if LANGDETECT_AVAILABLE:
            logger.info("MultilingualResumeParser: langdetect available — language detection enabled.")
    
    def parse_file(
        self,
        file_content: bytes,
        filename: str,
        use_ai: bool = False,
        detect_language: bool = True,
        translate_to_english: bool = True,
    ) -> Dict[str, Any]:
        # parsed dict gains: detected_language (always),
        # resume_text_original + translated resume_text (if non-English + translator available),
        # translation_error (if translate failed).
        parsed_data = super().parse_file(file_content, filename, use_ai)

        detected_language = "en"
        if detect_language and LANGDETECT_AVAILABLE:
            resume_text = parsed_data.get("resume_text", "")
            if resume_text:
                try:
                    detected_language = detect(resume_text)
                    logger.info("MultilingualResumeParser: detected language=%s", detected_language)
                except Exception:
                    logger.exception("MultilingualResumeParser: language detection failed; defaulting to 'en'.")
                    detected_language = "en"

        parsed_data["detected_language"] = detected_language

        if (
            translate_to_english
            and detected_language != "en"
            and self._translator_cls is not None
        ):
            resume_text = parsed_data.get("resume_text", "")
            if resume_text:
                try:
                    logger.info(
                        "MultilingualResumeParser: translating %s → en (%d chars).",
                        detected_language,
                        len(resume_text),
                    )
                    translated = self._translator_cls(
                        source=detected_language, target="en"
                    ).translate(resume_text)
                    parsed_data["resume_text_original"] = resume_text
                    parsed_data["resume_text"] = translated
                    logger.info("MultilingualResumeParser: translation complete.")
                except Exception:
                    logger.exception("MultilingualResumeParser: translation failed; keeping original text.")
                    parsed_data["translation_error"] = "Translation failed — see server logs."

        return parsed_data

    def parse_text_multilingual(self, text: str, language: Optional[str] = None) -> Dict[str, Any]:
        # parse raw text - BCP-47 language, auto-detected when None and langdetect present
        if language is None and LANGDETECT_AVAILABLE:
            try:
                language = detect(text)
            except Exception:
                logger.exception("MultilingualResumeParser: language detection failed in parse_text_multilingual.")
                language = "en"

        parsed_data = self._parse_text(text, text)
        parsed_data["detected_language"] = language or "en"
        return parsed_data

