# threaded notes on applications - recruiter collaboration
# GET list (newest first), POST add, DELETE own note only
# only the job-owning recruiter can read/write; author-only delete

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import require_recruiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["application-notes"])


def _serialise_note(note: models.ApplicationNote) -> dict:
    # shape one note for the API response
    return {
        "id": note.id,
        "application_id": note.application_id,
        "body": note.body,
        "created_at": note.created_at,
        "author": {
            "id": note.author.id,
            "email": note.author.email,
            "first_name": note.author.first_name,
            "last_name": note.author.last_name,
        },
    }


def _load_application_for_recruiter(
    application_id: int,
    db: Session,
    recruiter: models.User,
) -> models.Application:
    # fetch app and verify recruiter owns the job - 404 or 403
    application = (
        db.query(models.Application)
        .filter(models.Application.id == application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = (
        db.query(models.Job)
        .filter(models.Job.id == application.job_id)
        .first()
    )
    if not job or job.recruiter_id != recruiter.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to access notes on this application",
        )
    return application


# list notes
@router.get(
    "/{application_id}/notes",
    response_model=List[schemas.ApplicationNoteResponse],
)
def list_notes(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # all notes on this app, newest first
    _load_application_for_recruiter(application_id, db, current_user)

    # id tiebreaker - sqlite timestamps only have 1s resolution
    notes = (
        db.query(models.ApplicationNote)
        .filter(models.ApplicationNote.application_id == application_id)
        .order_by(
            models.ApplicationNote.created_at.desc(),
            models.ApplicationNote.id.desc(),
        )
        .all()
    )
    return [_serialise_note(n) for n in notes]


# create note
@router.post(
    "/{application_id}/notes",
    response_model=schemas.ApplicationNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    application_id: int,
    payload: schemas.ApplicationNoteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # add a note - current user becomes author
    _load_application_for_recruiter(application_id, db, current_user)

    note = models.ApplicationNote(
        application_id=application_id,
        author_id=current_user.id,
        body=payload.body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialise_note(note)


# delete note
@router.delete(
    "/{application_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_note(
    application_id: int,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_recruiter),
):
    # author only - job owner can't delete someone else's note
    _load_application_for_recruiter(application_id, db, current_user)

    note = (
        db.query(models.ApplicationNote)
        .filter(
            models.ApplicationNote.id == note_id,
            models.ApplicationNote.application_id == application_id,
        )
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author of a note can delete it",
        )

    db.delete(note)
    db.commit()
    return None
