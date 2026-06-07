# backend pytest config
# puts backend + ai on path, isolated sqlite db, client fixture with rate limits off

from __future__ import annotations

import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, os.pardir))

for path in (ROOT_DIR, BACKEND_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

# must set before any app.* import
_TEST_DB_PATH = os.path.join(BACKEND_DIR, "_test_smartrecruiter.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH.replace(os.sep, '/')}")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("EMBEDDING_BACKEND", "sbert")
os.environ.setdefault("LLM_PII_REDACTION", "True")

# force smtp off for whole session (override, not setdefault)
os.environ["SMTP_ENABLED"] = "False"


@pytest.fixture(scope="session")
def app_client():
    # session TestClient, rate limiter disabled
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)

    from fastapi.testclient import TestClient

    from app.rate_limit import limiter

    # slowapi 10/min on auth would slow the suite way down
    limiter.enabled = False

    from main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_db(app_client):
    # wipe tables before each test
    from app.database import Base, engine, SessionLocal

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # reverse fk order for sqlite
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()
    yield


# shared helpers for api tests

@pytest.fixture
def make_user(app_client):
    # register user, return (access_token, refresh_token, user_json)

    def _make(
        email: str,
        password: str = "Sup3rs3cret-pw!",
        role: str = "applicant",
        first_name: str = "Test",
        last_name: str = "User",
        company_name: str | None = None,
    ):
        payload = {
            "email": email,
            "password": password,
            "role": role,
            "first_name": first_name,
            "last_name": last_name,
        }
        if role == "recruiter":
            payload["company_name"] = company_name or "Acme Inc"
        r = app_client.post("/auth/register", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        return body["access_token"], body["refresh_token"], body["user"]

    return _make


@pytest.fixture
def auth_header():
    def _hdr(token: str):
        return {"Authorization": f"Bearer {token}"}
    return _hdr
