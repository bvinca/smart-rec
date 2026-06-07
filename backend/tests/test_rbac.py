# rbac: recruiter vs applicant routes, no cross-recruiter data leaks

from __future__ import annotations


def _create_job(client, recruiter_token):
    payload = {
        "title": "RBAC test job",
        "description": "We need a Python developer.",
        "requirements": "Python, FastAPI",
        "status": "active",
    }
    r = client.post(
        "/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_applicant_cannot_create_a_job(app_client, make_user, auth_header):
    applicant_tok, _, _ = make_user("a-app@example.com", role="applicant")
    r = app_client.post(
        "/jobs",
        json={"title": "x", "description": "y", "status": "active"},
        headers=auth_header(applicant_tok),
    )
    assert r.status_code == 403


def test_recruiter_cannot_access_applicant_dashboard_routes(app_client, make_user, auth_header):
    # /resume/upload allows any authed user; use require_applicant route instead
    recruiter_tok, _, _ = make_user(
        "r-app@example.com", role="recruiter", company_name="Acme"
    )
    r = app_client.post(
        "/applications/apply/1",
        headers=auth_header(recruiter_tok),
    )
    assert r.status_code == 403, r.text


def test_recruiter_cannot_read_another_recruiters_application(
    app_client, make_user, auth_header
):
    # applications.py:259 - must own the job
    recruiter_a_tok, _, _ = make_user("rec-a@example.com", role="recruiter")
    recruiter_b_tok, _, _ = make_user("rec-b@example.com", role="recruiter")
    applicant_tok, _, _ = make_user("app1@example.com", role="applicant")

    job = _create_job(app_client, recruiter_a_tok)

    apply_r = app_client.post(
        f"/applications/apply/{job['id']}",
        headers=auth_header(applicant_tok),
    )
    assert apply_r.status_code == 200, apply_r.text
    app_id = apply_r.json()["id"]

    leak_r = app_client.get(
        f"/applications/{app_id}",
        headers=auth_header(recruiter_b_tok),
    )
    assert leak_r.status_code == 403, leak_r.text

    own_r = app_client.get(
        f"/applications/{app_id}",
        headers=auth_header(recruiter_a_tok),
    )
    assert own_r.status_code == 200


def test_applicant_cannot_read_another_applicants_application(
    app_client, make_user, auth_header
):
    # applications.py:255 - applicants see own apps only
    recruiter_tok, _, _ = make_user("rec-c@example.com", role="recruiter")
    applicant_1_tok, _, _ = make_user("alice-c@example.com", role="applicant")
    applicant_2_tok, _, _ = make_user("bob-c@example.com", role="applicant")

    job = _create_job(app_client, recruiter_tok)
    apply_r = app_client.post(
        f"/applications/apply/{job['id']}",
        headers=auth_header(applicant_1_tok),
    )
    assert apply_r.status_code == 200, apply_r.text
    app_id = apply_r.json()["id"]

    leak_r = app_client.get(
        f"/applications/{app_id}",
        headers=auth_header(applicant_2_tok),
    )
    assert leak_r.status_code == 403, leak_r.text
