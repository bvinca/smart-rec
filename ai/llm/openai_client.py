# Thin OpenAI wrapper - exponential backoff retry + structured logging.

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Dict, List, Optional

# make backend importable when this runs as a standalone script
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings  # type: ignore
except Exception:  # pragma: no cover
    class _Fallback:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

    settings = _Fallback()  # type: ignore

logger = logging.getLogger(__name__)


class OpenAIClient:
    # OpenAI API wrapper with exponential backoff retry

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        api_key = (settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set; LLM features are disabled.")
        if not api_key.startswith(("sk-", "sk_")):
            raise ValueError("OPENAI_API_KEY does not look like a valid key.")

        try:
            from openai import OpenAI  # local import - optional dep
        except ImportError as exc:  # pragma: no cover - requirements should pin it
            raise ValueError(
                "The 'openai' package is not installed. Run `pip install openai` "
                "or unset OPENAI_API_KEY to use the local Sentence-BERT path."
            ) from exc

        self.client = OpenAI(api_key=api_key)
        self.default_model = getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4o-mini")
        self.default_embedding_model = getattr(
            settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # chat
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        # chat.completions with exponential backoff retry
        model = model or self.default_model
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                content = response.choices[0].message.content or ""
                return content.strip()
            except Exception as exc:  # pragma: no cover - network errors
                last_error = exc
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "OpenAI chat error (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, self.max_retries, exc, wait,
                    )
                    time.sleep(wait)

        logger.error("OpenAI chat call failed after %d attempts: %s", self.max_retries, last_error)
        raise last_error if last_error else RuntimeError("OpenAI chat call failed.")

    # embeds
    def embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        # single-text embedding via OpenAI. Use SBERT for free local embeddings.
        model = model or self.default_embedding_model
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(model=model, input=text[:8000])
                return list(response.data[0].embedding)
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "OpenAI embedding error (attempt %d/%d): %s. Retrying...",
                        attempt + 1, self.max_retries, exc,
                    )
                    time.sleep(wait)

        logger.error("OpenAI embedding failed after %d attempts: %s", self.max_retries, last_error)
        raise last_error if last_error else RuntimeError("OpenAI embedding call failed.")
