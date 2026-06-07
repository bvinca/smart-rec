# fastapi boot smoke tests

from __future__ import annotations


def test_health(app_client):
    response = app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_advertises_embedding_backend(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SmartRecruiter API Running"
    assert payload["embedding_backend"] in {"sbert", "openai"}
