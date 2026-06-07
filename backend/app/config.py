# env-driven settings. never ships a real key and refuses to boot with the
# placeholder SECRET_KEY outside DEBUG mode.

from __future__ import annotations

import logging
import secrets
from typing import List, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


_DEFAULT_SECRET_PLACEHOLDER = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ----- Database -----
    DATABASE_URL: str = "sqlite:///./smartrecruiter.db"

    # ----- OpenAI (optional) -----
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    # ----- Local model selection -----
    # "sbert"  = Sentence-BERT (default, all-MiniLM-L6-v2, 384 dim)
    # "openai" = OpenAI embeddings (3072 dim)
    # "auto"   = openai if a key is set, else sbert
    EMBEDDING_BACKEND: str = "sbert"
    SBERT_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ----- Auth / security -----
    SECRET_KEY: str = _DEFAULT_SECRET_PLACEHOLDER
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ----- Server -----
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # ----- ChromaDB -----
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # ----- CORS -----
    # plain string so pydantic-settings doesn't try to JSON-decode it.
    # `cors_origins_list` parses it. accepts CSV or JSON-array form.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ----- Email / SMTP -----
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "SmartRecruiter"
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT: int = 10

    # ----- Uploads -----
    # hard cap on résumé upload size. enforced while streaming so an oversized
    # file can't be buffered into memory (DoS guard).
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB

    # ----- Privacy -----
    # strip PII (names, emails, phones, addresses) from anything sent to an
    # external LLM - part of the blind-screening setup.
    LLM_PII_REDACTION: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _normalise_cors(cls, value: object) -> str:
        # accept CSV / JSON-array / list, store as CSV. runs pre-coercion so
        # we always see the raw value.
        import json

        if isinstance(value, list):
            return ",".join(str(v).strip() for v in value if str(v).strip())
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return "http://localhost:3000,http://localhost:5173"
            # Accept JSON-array syntax: '["http://...", ...]'
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    return ",".join(str(v).strip() for v in parsed if str(v).strip())
                except json.JSONDecodeError:
                    pass
            return stripped
        return "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        # parsed list of origins, with a guard against the wildcard
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS must not contain '*'. "
                "Specify explicit origins (e.g. 'http://localhost:3000')."
            )
        return origins

    @field_validator("EMBEDDING_BACKEND")
    @classmethod
    def _validate_backend(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"sbert", "openai", "auto"}:
            raise ValueError("EMBEDDING_BACKEND must be one of 'sbert', 'openai', 'auto'.")
        return value

    def resolved_embedding_backend(self) -> str:
        # collapse "auto" to a concrete backend at runtime
        if self.EMBEDDING_BACKEND != "auto":
            return self.EMBEDDING_BACKEND
        return "openai" if self.OPENAI_API_KEY.strip() else "sbert"

    def ensure_secret_key(self) -> None:
        # refuse to boot with the placeholder secret outside DEBUG mode
        if self.SECRET_KEY == _DEFAULT_SECRET_PLACEHOLDER or not self.SECRET_KEY:
            if self.DEBUG:
                # per-process key - dev tokens shouldn't survive a restart
                self.SECRET_KEY = secrets.token_urlsafe(48)
                logger.warning(
                    "SECRET_KEY is unset or default; generated an ephemeral key for this process. "
                    "Set SECRET_KEY in .env before deploying."
                )
            else:
                raise RuntimeError(
                    "SECRET_KEY is unset or set to the default placeholder. "
                    "Refusing to start in non-debug mode. Set SECRET_KEY in the environment."
                )


settings = Settings()
settings.ensure_secret_key()
