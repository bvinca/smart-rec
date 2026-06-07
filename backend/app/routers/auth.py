# auth - register, login, refresh, logout, password change + reset
from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.rate_limit import AUTH_LIMIT, limiter
from app.services.auth_service import (
    authenticate_user,
    consume_password_reset_token,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_user,
    get_password_hash,
    get_user_by_email,
    revoke_all_refresh_tokens,
    rotate_refresh_token,
    update_user_password,
    verify_password,
)
from app.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class _RefreshRequest(BaseModel):
    refresh_token: str


def _user_response(user: models.User) -> schemas.UserResponse:
    return schemas.UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        company_name=user.company_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/register", response_model=schemas.Token)
@limiter.limit(AUTH_LIMIT)
def register(
    request: Request,
    user_data: schemas.UserRegister,
    db: Session = Depends(get_db),
):
    # new user signup - returns access + refresh tokens
    if user_data.role not in {"applicant", "recruiter"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'applicant' or 'recruiter'",
        )
    if user_data.role == "recruiter" and not user_data.company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name is required for recruiters",
        )
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    db_user = create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        company_name=user_data.company_name,
    )

    access_token = create_access_token(
        data={"sub": db_user.email, "role": db_user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(db, db_user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _user_response(db_user),
    }


@router.post("/login", response_model=schemas.Token)
@limiter.limit(AUTH_LIMIT)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # email + password -> token pair
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.post("/refresh", response_model=schemas.Token)
@limiter.limit(AUTH_LIMIT)
def refresh(
    request: Request,
    body: _RefreshRequest,
    db: Session = Depends(get_db),
):
    # swap refresh token for new pair - old one revoked on use (rotation)
    # replaying a revoked token kills the whole family (theft signal)
    user, new_refresh_token = rotate_refresh_token(db, body.refresh_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    # who's logged in
    return current_user


@router.post("/logout")
def logout(
    body: _RefreshRequest = Body(default=_RefreshRequest(refresh_token="")),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # revoke all refresh tokens - client should drop access token too (short TTL)
    if body.refresh_token:
        revoke_all_refresh_tokens(db, current_user.id)
    return {"message": "Successfully logged out"}


@router.post("/change-password")
@limiter.limit(AUTH_LIMIT)
def change_password(
    request: Request,
    body: schemas.PasswordChangeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # logged-in password change - needs current pw, revokes all refresh tokens
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password.",
        )
    current_user.hashed_password = get_password_hash(body.new_password)
    db.add(current_user)
    db.commit()
    # nuke refresh tokens - compromised sessions have to re-login
    revoke_all_refresh_tokens(db, current_user.id)
    return {"message": "Password updated. Please log in again on other devices."}


@router.post("/request-password-reset")
@limiter.limit(AUTH_LIMIT)
def request_password_reset(
    request: Request,
    body: schemas.PasswordResetRequest,
    db: Session = Depends(get_db),
):
    # forgot password - always 200 (no email enumeration)
    # SMTP if configured, else DEBUG echoes token for dev
    user = get_user_by_email(db, body.email)
    response = {
        "message": (
            "If an account exists for that email, a password-reset link has "
            "been sent."
        ),
    }
    if user is None or not user.is_active:
        # same response either way - don't leak if email exists
        logger.info("Password-reset requested for unknown email; returning 200.")
        return response

    raw_token = create_password_reset_token(db, user.id)
    reset_url = f"/reset-password?token={raw_token}"
    logger.info(
        "Password-reset link for user_id=%d: %s (expires in 30 min)",
        user.id, reset_url,
    )

    # SMTP send never raises - False means fall back to DEBUG echo
    delivered = send_password_reset_email(
        to_email=user.email,
        reset_url=reset_url,
    )
    if delivered:
        logger.info("Password-reset email delivered to %s.", user.email)
    else:
        logger.info(
            "Password-reset email NOT delivered to %s (SMTP disabled or "
            "delivery failed). DEBUG echo will be used if available.",
            user.email,
        )

    # DEBUG=True: echo token so tests/dev work without SMTP
    if getattr(settings, "DEBUG", False):
        response["debug_token"] = raw_token
        response["debug_reset_url"] = reset_url
        response["smtp_delivered"] = delivered
    return response


@router.post("/confirm-password-reset")
@limiter.limit(AUTH_LIMIT)
def confirm_password_reset(
    request: Request,
    body: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    # finish reset - single-use token, revokes refresh tokens on success
    user = consume_password_reset_token(db, body.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid, expired, or already used.",
        )
    update_user_password(db, user, body.new_password)
    return {"message": "Password reset. Please log in with the new password."}
