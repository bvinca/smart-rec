# auth route tests: bcrypt, jwt access, rotating refresh + reuse detection

from __future__ import annotations


def test_register_returns_access_and_refresh_tokens(app_client, make_user):
    token, refresh, user = make_user("alice@example.com", role="applicant")
    assert token and refresh
    assert user["email"] == "alice@example.com"
    assert user["role"] == "applicant"


def test_login_with_wrong_password_returns_401(app_client, make_user):
    make_user("bob@example.com", password="Correct-pw-1!")
    r = app_client.post(
        "/auth/login",
        data={"username": "bob@example.com", "password": "wrong-password!!"},
    )
    assert r.status_code == 401
    assert "incorrect" in r.json()["detail"].lower()


def test_me_returns_current_user(app_client, make_user, auth_header):
    token, _, user = make_user("carol@example.com")
    r = app_client.get("/auth/me", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["email"] == user["email"]


def test_refresh_rotates_and_revokes_old_token(app_client, make_user):
    # refresh tokens are single-use
    _, refresh, _ = make_user("dan@example.com")
    r1 = app_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh and new_refresh != refresh

    r2 = app_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401


def test_reused_refresh_token_revokes_entire_family(app_client, make_user):
    # replay revoked token kills the whole family (auth_service.py:111)
    _, refresh, _ = make_user("erin@example.com")
    r = app_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]

    replay = app_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401

    after = app_client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401, (
        "Reuse detection failed: live token in same family was not revoked."
    )


# POST /auth/change-password

def test_change_password_with_correct_current_password_succeeds(
    app_client, make_user, auth_header
):
    token, refresh, _ = make_user("eve@example.com", password="Old-pw-2026!")
    r = app_client.post(
        "/auth/change-password",
        json={"current_password": "Old-pw-2026!", "new_password": "Brand-New-pw-2026!"},
        headers=auth_header(token),
    )
    assert r.status_code == 200, r.text
    bad = app_client.post(
        "/auth/login",
        data={"username": "eve@example.com", "password": "Old-pw-2026!"},
    )
    assert bad.status_code == 401
    good = app_client.post(
        "/auth/login",
        data={"username": "eve@example.com", "password": "Brand-New-pw-2026!"},
    )
    assert good.status_code == 200


def test_change_password_with_wrong_current_password_returns_400(
    app_client, make_user, auth_header
):
    token, _, _ = make_user("frank@example.com", password="Real-pw-2026!")
    r = app_client.post(
        "/auth/change-password",
        json={"current_password": "wrong-pw!", "new_password": "Other-pw-2026!"},
        headers=auth_header(token),
    )
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"].lower()


def test_change_password_rejects_same_value(app_client, make_user, auth_header):
    token, _, _ = make_user("greta@example.com", password="Same-pw-2026!")
    r = app_client.post(
        "/auth/change-password",
        json={"current_password": "Same-pw-2026!", "new_password": "Same-pw-2026!"},
        headers=auth_header(token),
    )
    assert r.status_code == 400


def test_change_password_revokes_refresh_tokens(app_client, make_user, auth_header):
    token, refresh, _ = make_user("hank@example.com", password="Was-pw-2026!")
    r = app_client.post(
        "/auth/change-password",
        json={"current_password": "Was-pw-2026!", "new_password": "Now-pw-2026!"},
        headers=auth_header(token),
    )
    assert r.status_code == 200
    used = app_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert used.status_code == 401


# forgot-password / reset: POST /auth/request-password-reset, POST /auth/confirm-password-reset

def _request_reset(app_client, email: str):
    return app_client.post("/auth/request-password-reset", json={"email": email})


def test_request_reset_for_unknown_email_returns_200_no_leak(app_client):
    # unknown email still 200, no account enumeration
    r = _request_reset(app_client, "nobody@example.com")
    assert r.status_code == 200
    body = r.json()
    assert "message" in body
    assert "debug_token" not in body


def test_request_reset_for_known_email_issues_token(app_client, make_user):
    make_user("iris@example.com", password="Old-pw-2026!")
    r = _request_reset(app_client, "iris@example.com")
    assert r.status_code == 200
    body = r.json()
    # conftest sets DEBUG=True so token shows up for tests
    assert body.get("debug_token"), "debug_token expected in DEBUG mode"


def test_confirm_reset_with_valid_token_updates_password(app_client, make_user):
    make_user("jay@example.com", password="Old-pw-2026!")
    raw_token = _request_reset(app_client, "jay@example.com").json()["debug_token"]

    confirm = app_client.post(
        "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "Fresh-pw-2026!"},
    )
    assert confirm.status_code == 200, confirm.text

    bad = app_client.post(
        "/auth/login",
        data={"username": "jay@example.com", "password": "Old-pw-2026!"},
    )
    assert bad.status_code == 401
    good = app_client.post(
        "/auth/login",
        data={"username": "jay@example.com", "password": "Fresh-pw-2026!"},
    )
    assert good.status_code == 200


def test_confirm_reset_token_is_single_use(app_client, make_user):
    make_user("kim@example.com", password="Old-pw-2026!")
    raw_token = _request_reset(app_client, "kim@example.com").json()["debug_token"]

    first = app_client.post(
        "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "First-pw-2026!"},
    )
    assert first.status_code == 200
    replay = app_client.post(
        "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "Second-pw-2026!"},
    )
    assert replay.status_code == 400
    assert (
        "invalid" in replay.json()["detail"].lower()
        or "used" in replay.json()["detail"].lower()
    )


def test_confirm_reset_with_unknown_token_returns_400(app_client):
    r = app_client.post(
        "/auth/confirm-password-reset",
        json={"token": "never-issued", "new_password": "Whatever-pw-2026!"},
    )
    assert r.status_code == 400


def test_confirm_reset_revokes_outstanding_refresh_tokens(app_client, make_user):
    # reset kills all active sessions
    _, refresh, _ = make_user("liam@example.com", password="Was-pw-2026!")
    raw_token = _request_reset(app_client, "liam@example.com").json()["debug_token"]

    confirm = app_client.post(
        "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "Now-pw-2026!"},
    )
    assert confirm.status_code == 200
    used = app_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert used.status_code == 401


def test_confirm_reset_rejects_weak_new_password(app_client, make_user):
    # pydantic rejects <8 chars before db touch
    make_user("mia@example.com", password="Was-pw-2026!")
    raw_token = _request_reset(app_client, "mia@example.com").json()["debug_token"]
    r = app_client.post(
        "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "short"},
    )
    assert r.status_code == 422
