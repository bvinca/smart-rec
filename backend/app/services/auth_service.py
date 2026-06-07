from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models
from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# refresh tokens are opaque random strings - only the SHA-256 hash hits the DB.
REFRESH_TOKEN_BYTES = 48
REFRESH_TOKEN_EXPIRE_DAYS = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # plain vs bcrypt hash
    # bcrypt caps inputs at 72 bytes - trim if we go over
    if isinstance(plain_password, str):
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            plain_password = password_bytes[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    # bcrypt cost factor 12 (passlib default), 72-byte input cap
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            # trim without breaking a multi-byte char on the boundary
            password = password_bytes[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    # short-lived JWT (default 60 min via settings)
    from datetime import timedelta  # local - keeps top-of-file tidy

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    # returns the decoded payload or None on any failure
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── refresh-token helpers ─────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token(db: Session, user_id: int) -> str:
    # mint a new token, persist its hash, return the raw value
    from datetime import timedelta  # local - keeps top-of-file tidy

    raw = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    record = models.RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    logger.debug("Refresh token issued for user_id=%d", user_id)
    return raw


def rotate_refresh_token(
    db: Session, raw_token: str
) -> tuple[Optional[models.User], Optional[str]]:
    # validate the token, burn it, mint a fresh one.
    # returns (user, new_raw_token) on success, (None, None) on any miss.
    # reuse of a revoked token = nuke the whole family for the user.
    token_hash = _hash_token(raw_token)
    record: Optional[models.RefreshToken] = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == token_hash)
        .first()
    )

    if record is None:
        logger.warning("Refresh token not found — possible token theft.")
        return None, None

    now = datetime.now(timezone.utc)

    if record.revoked:
        # token reuse - kill the whole family
        logger.warning(
            "Revoked refresh token reused for user_id=%d — revoking all tokens.",
            record.user_id,
        )
        (
            db.query(models.RefreshToken)
            .filter(
                models.RefreshToken.user_id == record.user_id,
                models.RefreshToken.revoked == False,  # noqa: E712
            )
            .update({"revoked": True})
        )
        db.commit()
        return None, None

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as _tz
        expires_at = expires_at.replace(tzinfo=_tz.utc)

    if expires_at < now:
        record.revoked = True
        db.commit()
        logger.info("Refresh token expired for user_id=%d.", record.user_id)
        return None, None

    # all good - burn the old, mint a new
    record.revoked = True
    db.commit()

    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user or not user.is_active:
        return None, None

    new_raw = create_refresh_token(db, user.id)
    return user, new_raw


def revoke_all_refresh_tokens(db: Session, user_id: int) -> None:
    # logout / password change calls this
    (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked == False,  # noqa: E712
        )
        .update({"revoked": True})
    )
    db.commit()


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    # email + password check, returns the user or None
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, email: str, password: str, role: str, first_name: str = None, last_name: str = None, company_name: str = None) -> models.User:
    hashed_password = get_password_hash(password)
    db_user = models.User(
        email=email,
        hashed_password=hashed_password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        company_name=company_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ── password-reset helpers ────────────────────────────────────────────────────
# same storage trick as RefreshToken: hand the raw value to the caller
# (SMTP in prod, debug echo in dev), persist only the SHA-256 hash.

PASSWORD_RESET_TOKEN_BYTES = 32          # 256 bits of entropy
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30  # short-lived on purpose


def create_password_reset_token(db: Session, user_id: int) -> str:
    # caller is responsible for getting the raw value to the user out-of-band
    from datetime import timedelta

    raw = secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    record = models.PasswordResetToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    logger.info(
        "Password-reset token issued for user_id=%d (expires in %d min)",
        user_id, PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    )
    return raw


def consume_password_reset_token(
    db: Session, raw_token: str
) -> Optional[models.User]:
    # validate + mark used. returns the user on success, None on any miss
    # (unknown / expired / used / inactive). on success every refresh token
    # for the user is also revoked.
    token_hash = _hash_token(raw_token)
    record: Optional[models.PasswordResetToken] = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if record is None:
        logger.warning("Password-reset token not found (possible probe).")
        return None

    now = datetime.now(timezone.utc)
    if record.used_at is not None:
        logger.warning(
            "Password-reset token reuse attempt for user_id=%d.", record.user_id
        )
        return None

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as _tz
        expires_at = expires_at.replace(tzinfo=_tz.utc)
    if expires_at < now:
        logger.info("Password-reset token expired for user_id=%d.", record.user_id)
        return None

    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user or not user.is_active:
        return None

    record.used_at = now
    db.commit()
    revoke_all_refresh_tokens(db, user.id)
    return user


def update_user_password(db: Session, user: models.User, new_password: str) -> None:
    # password is assumed validated by the schema layer already
    user.hashed_password = get_password_hash(new_password)
    db.add(user)
    db.commit()

