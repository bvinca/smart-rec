# central log setup - structured, levelled, replaces the `print` statements
# from the very first prototype.

from __future__ import annotations

import logging
import logging.config
import os
import sys

_DEFAULT_FORMAT = (
    "%(asctime)s %(levelname)-7s %(name)s :: %(message)s"
)


def configure_logging(level: str | int | None = None) -> None:
    # idempotent - main.py and the test fixtures both call this. honours LOG_LEVEL.
    resolved_level = level or os.environ.get("LOG_LEVEL", "INFO")
    if isinstance(resolved_level, str):
        resolved_level = resolved_level.upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": _DEFAULT_FORMAT,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "default",
                    "level": resolved_level,
                },
            },
            "root": {
                "handlers": ["console"],
                "level": resolved_level,
            },
            "loggers": {
                # quiet the noisy third-party loggers
                "uvicorn.access": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
                "openai": {"level": "WARNING"},
                "chromadb": {"level": "WARNING"},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    # tiny wrapper so callers don't import `logging` themselves
    return logging.getLogger(name)
