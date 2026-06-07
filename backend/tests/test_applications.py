# apply lifecycle + upload validation tests
# ai_status transitions, magic-byte check, size cap (item 3)

from __future__ import annotations

import io


def _create_job(client, recruiter_token, status: str = "active"):
    payload = {
        "title": "Apply lifecycle test job",
        "description": "Hiring a Python developer.",
        "requirements": "Python, FastAPI",
        "status": status,
    }
    r = client.post(
        "/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_apply_without_file_sets_ai_status_skipped(app_client, make_user, auth_header):
    rec_tok, _, _ = make_user("rec-apply-1@example.com", role="recruiter")
    app_tok, _, _ = make_user("alice-apply-1@example.com", role="applicant")
    job = _create_job(app_client, rec_tok)

    r = app_client.post(
        f"/applications/apply/{job['id']}",
        headers=auth_header(app_tok),
    )
    assert r.status_code == 200, r.text
    assert r.json()["ai_status"] == "skipped"


def test_duplicate_application_returns_400(app_client, make_user, auth_header):
    rec_tok, _, _ = make_user("rec-apply-2@example.com", role="recruiter")
    app_tok, _, _ = make_user("alice-apply-2@example.com", role="applicant")
    job = _create_job(app_client, rec_tok)

    r1 = app_client.post(f"/applications/apply/{job['id']}", headers=auth_header(app_tok))
    assert r1.status_code == 200, r1.text
    r2 = app_client.post(f"/applications/apply/{job['id']}", headers=auth_header(app_tok))
    assert r2.status_code == 400
    assert "already applied" in r2.json()["detail"].lower()


def test_apply_to_inactive_job_returns_400(app_client, make_user, auth_header):
    rec_tok, _, _ = make_user("rec-apply-3@example.com", role="recruiter")
    app_tok, _, _ = make_user("alice-apply-3@example.com", role="applicant")
    job = _create_job(app_client, rec_tok, status="closed")

    r = app_client.post(f"/applications/apply/{job['id']}", headers=auth_header(app_tok))
    assert r.status_code == 400, r.text


def test_apply_rejects_renamed_binary_by_magic_bytes(app_client, make_user, auth_header):
    # pe exe renamed to .pdf should fail magic-byte sniff, not just extension
    rec_tok, _, _ = make_user("rec-apply-4@example.com", role="recruiter")
    app_tok, _, _ = make_user("alice-apply-4@example.com", role="applicant")
    job = _create_job(app_client, rec_tok)

    fake_pdf = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
    r = app_client.post(
        f"/applications/apply/{job['id']}",
        headers=auth_header(app_tok),
        files={"file": ("cv.pdf", fake_pdf, "application/pdf")},
    )
    assert r.status_code == 400, r.text
    detail = r.json()["detail"].lower()
    assert "content does not match" in detail or "not a supported document" in detail


def test_resume_upload_rejects_disallowed_extension(app_client, make_user, auth_header):
    # .exe blocked at extension check before sniff or disk write
    app_tok, _, _ = make_user("alice-apply-5@example.com", role="applicant")
    fake_exe = io.BytesIO(b"MZ\x90\x00")
    r = app_client.post(
        "/resume/upload",
        headers=auth_header(app_tok),
        files={"file": ("payload.exe", fake_exe, "application/octet-stream")},
    )
    assert r.status_code == 400, r.text
    assert "invalid file type" in r.json()["detail"].lower()


# interview prep: POST /applications/{id}/interview-prep (llm patched out)

import pytest  # noqa: E402


_STUB_PREP = {
    "company_overview": "A test-only company that builds boring CRUD apps.",
    "position_questions": [
        "Walk me through your strongest project.",
        "How do you debug a slow SQL query?",
        "How do you handle conflicting product priorities?",
        "Tell me about a time you disagreed with a teammate.",
        "Why this company specifically?",
    ],
    "preparation_tips": [
        "Skim the company's public engineering blog.",
        "Have one war-story per CV bullet ready.",
        "Bring two questions for the interviewer.",
        "Practise explaining a recent decision in 90 seconds.",
    ],
}


def _seed_application_with_applicant(app_client, recruiter_token, applicant_token, auth_header):
    # job + apply without file, then attach Applicant row for interview-prep precondition
    from app.database import SessionLocal
    from app import models

    job = _create_job(app_client, recruiter_token)
    apply_resp = app_client.post(
        f"/applications/apply/{job['id']}", headers=auth_header(applicant_token)
    )
    assert apply_resp.status_code == 200, apply_resp.text
    application_id = apply_resp.json()["id"]

    db = SessionLocal()
    try:
        applicant_row = models.Applicant(
            job_id=job["id"],
            first_name="Test",
            last_name="Applicant",
            email="alice-prep@example.com",
            skills=["Python", "PostgreSQL"],
        )
        db.add(applicant_row)
        db.commit()
        db.refresh(applicant_row)
        application = db.query(models.Application).filter(
            models.Application.id == application_id
        ).first()
        application.applicant_id = applicant_row.id
        db.commit()
        return application_id
    finally:
        db.close()


def test_interview_prep_returns_payload_and_caches(
    app_client, make_user, auth_header, monkeypatch
):
    # first call generates; second hits cache (llm not called again)
    rec_tok, _, _ = make_user("rec-prep-1@example.com", role="recruiter")
    app_tok, _, _ = make_user("alice-prep-1@example.com", role="applicant")
    application_id = _seed_application_with_applicant(
        app_client, rec_tok, app_tok, auth_header
    )

    call_count = {"n": 0}

    def fake_generate(**kwargs):
        call_count["n"] += 1
        return _STUB_PREP

    import ai.llm.interview_prep_generator as gen_mod
    monkeypatch.setattr(gen_mod, "generate_interview_prep", fake_generate)

    r1 = app_client.post(
        f"/applications/{application_id}/interview-prep",
        headers=auth_header(app_tok),
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["cached"] is False
    assert body1["company_overview"].startswith("A test-only")
    assert len(body1["position_questions"]) == 5
    assert 4 <= len(body1["preparation_tips"]) <= 6
    assert call_count["n"] == 1

    r2 = app_client.post(
        f"/applications/{application_id}/interview-prep",
        headers=auth_header(app_tok),
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["cached"] is True
    assert body2["company_overview"] == body1["company_overview"]
    assert call_count["n"] == 1, "LLM should not be called again on cache hit"


def test_interview_prep_rejects_other_users_application(
    app_client, make_user, auth_header
):
    # wrong applicant gets 403
    rec_tok, _, _ = make_user("rec-prep-2@example.com", role="recruiter")
    app_tok_a, _, _ = make_user("alice-prep-2@example.com", role="applicant")
    app_tok_b, _, _ = make_user("bob-prep-2@example.com", role="applicant")
    application_id = _seed_application_with_applicant(
        app_client, rec_tok, app_tok_a, auth_header
    )

    r = app_client.post(
        f"/applications/{application_id}/interview-prep",
        headers=auth_header(app_tok_b),
    )
    assert r.status_code == 403


def test_interview_prep_400_when_no_applicant_row(
    app_client, make_user, auth_header
):
    # no parsed cv/applicant row yet -> 400 not 5xx
    rec_tok, _, _ = make_user("rec-prep-3@example.com", role="recruiter")
    app_tok, _, _ = make_user("alice-prep-3@example.com", role="applicant")
    job = _create_job(app_client, rec_tok)
    apply_resp = app_client.post(
        f"/applications/apply/{job['id']}", headers=auth_header(app_tok)
    )
    application_id = apply_resp.json()["id"]
    # deliberately no Applicant row attached

    r = app_client.post(
        f"/applications/{application_id}/interview-prep",
        headers=auth_header(app_tok),
    )
    assert r.status_code == 400
    assert "cv" in r.json()["detail"].lower()
