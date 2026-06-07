# application notes api tests
# list/create/delete, rbac, author-only delete, validation

from __future__ import annotations

import pytest


def _make_job(client, recruiter_token, title: str = "Engineer") -> int:
    r = client.post(
        "/jobs/",
        json={
            "title": title,
            "description": "A job. We do things.",
            "requirements": "Some skills.",
            "status": "active",
        },
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _make_application(client, applicant_token, job_id: int) -> int:
    # apply without cv file still creates Application row
    r = client.post(
        f"/applications/apply/{job_id}",
        headers={"Authorization": f"Bearer {applicant_token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


class TestNotesHappyPath:
    def test_create_list_delete_roundtrip(self, app_client, make_user, auth_header):
        rec_token, _, rec = make_user("owner@co.com", role="recruiter")
        applicant_token, _, _ = make_user("applicant@x.com")
        job_id = _make_job(app_client, rec_token, title="Owner Job")
        app_id = _make_application(app_client, applicant_token, job_id)

        r = app_client.get(f"/applications/{app_id}/notes", headers=auth_header(rec_token))
        assert r.status_code == 200
        assert r.json() == []

        r = app_client.post(
            f"/applications/{app_id}/notes",
            json={"body": "Promising candidate, follow up next week."},
            headers=auth_header(rec_token),
        )
        assert r.status_code == 201, r.text
        note = r.json()
        assert note["body"] == "Promising candidate, follow up next week."
        assert note["author"]["email"] == "owner@co.com"
        assert note["application_id"] == app_id
        note_id = note["id"]

        r = app_client.get(f"/applications/{app_id}/notes", headers=auth_header(rec_token))
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["id"] == note_id

        r = app_client.delete(
            f"/applications/{app_id}/notes/{note_id}",
            headers=auth_header(rec_token),
        )
        assert r.status_code == 204

        r = app_client.get(f"/applications/{app_id}/notes", headers=auth_header(rec_token))
        assert r.json() == []

    def test_notes_returned_newest_first(self, app_client, make_user, auth_header):
        rec_token, _, _ = make_user("rec@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, rec_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        for body in ("first", "second", "third"):
            r = app_client.post(
                f"/applications/{app_id}/notes",
                json={"body": body},
                headers=auth_header(rec_token),
            )
            assert r.status_code == 201

        r = app_client.get(f"/applications/{app_id}/notes", headers=auth_header(rec_token))
        bodies = [n["body"] for n in r.json()]
        assert bodies == ["third", "second", "first"]


class TestNotesAccessControl:
    def test_applicant_cannot_list_notes(self, app_client, make_user, auth_header):
        rec_token, _, _ = make_user("rec@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, rec_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        r = app_client.get(
            f"/applications/{app_id}/notes",
            headers=auth_header(applicant_token),
        )
        assert r.status_code == 403

    def test_applicant_cannot_create_note(self, app_client, make_user, auth_header):
        rec_token, _, _ = make_user("rec@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, rec_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        r = app_client.post(
            f"/applications/{app_id}/notes",
            json={"body": "hi"},
            headers=auth_header(applicant_token),
        )
        assert r.status_code == 403

    def test_other_recruiter_cannot_read_notes(self, app_client, make_user, auth_header):
        owner_token, _, _ = make_user("owner@co.com", role="recruiter", company_name="Owner Co")
        other_token, _, _ = make_user("other@co.com", role="recruiter", company_name="Other Co")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, owner_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        r = app_client.get(f"/applications/{app_id}/notes", headers=auth_header(other_token))
        assert r.status_code == 403

    def test_other_recruiter_cannot_create_note(self, app_client, make_user, auth_header):
        owner_token, _, _ = make_user("owner@co.com", role="recruiter")
        other_token, _, _ = make_user("other@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, owner_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        r = app_client.post(
            f"/applications/{app_id}/notes",
            json={"body": "should be blocked"},
            headers=auth_header(other_token),
        )
        assert r.status_code == 403


class TestAuthorOnlyDelete:
    def test_other_user_cannot_delete_someone_elses_note(
        self, app_client, make_user, auth_header
    ):
        # cross-recruiter 403 already covered; here we db-insert applicant-authored note
        rec_token, _, owner = make_user("owner@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, rec_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        from app.database import SessionLocal
        from app import models

        db = SessionLocal()
        try:
            note = models.ApplicationNote(
                application_id=app_id,
                author_id=models.User and db.query(models.User).filter(
                    models.User.email == "a@x.com"
                ).first().id,
                body="not the owner's note",
            )
            db.add(note)
            db.commit()
            note_id = note.id
        finally:
            db.close()

        r = app_client.delete(
            f"/applications/{app_id}/notes/{note_id}",
            headers=auth_header(rec_token),
        )
        assert r.status_code == 403


class TestNoteValidation:
    def test_empty_body_rejected(self, app_client, make_user, auth_header):
        rec_token, _, _ = make_user("rec@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, rec_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        for body in ("", "   ", "\n\t  \n"):
            r = app_client.post(
                f"/applications/{app_id}/notes",
                json={"body": body},
                headers=auth_header(rec_token),
            )
            assert r.status_code == 422, r.text

    def test_oversized_body_rejected(self, app_client, make_user, auth_header):
        rec_token, _, _ = make_user("rec@co.com", role="recruiter")
        applicant_token, _, _ = make_user("a@x.com")
        job_id = _make_job(app_client, rec_token)
        app_id = _make_application(app_client, applicant_token, job_id)

        oversized = "x" * 4500
        r = app_client.post(
            f"/applications/{app_id}/notes",
            json={"body": oversized},
            headers=auth_header(rec_token),
        )
        assert r.status_code == 422
