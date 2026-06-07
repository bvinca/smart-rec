# shared SlowAPI limiter. import `limiter` and use `@limiter.limit(...)`.
# middleware + exception handler wired up in main.py.
#
# limits:
#   AUTH_LIMIT = 10/min - login, register, reset
#   AI_LIMIT   = 20/min - anything that touches the AI pipeline
#   default    = 60/min - everything else
# keyed by remote IP.
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

AUTH_LIMIT = "10/minute"
AI_LIMIT = "20/minute"
