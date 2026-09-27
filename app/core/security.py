"""Password hashing and JSON Web Token helpers."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh", "reset", "verify"]

#: bcrypt silently ignores anything past 72 bytes, so long passwords would all
#: collide on their first 72. Pre-hashing with SHA-256 keeps the full entropy.
_BCRYPT_MAX_BYTES = 72
BCRYPT_ROUNDS = 12


def _prepare(raw_password: str) -> bytes:
    encoded = raw_password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        import base64
        import hashlib

        return base64.b64encode(hashlib.sha256(encoded).digest())
    return encoded


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(
        _prepare(raw_password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("utf-8")


def verify_password(raw_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_prepare(raw_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True when a stored hash predates the current cost factor."""
    try:
        return int(hashed_password.split("$")[2]) < BCRYPT_ROUNDS
    except (IndexError, ValueError):
        return True


def _create_token(
    subject: str | int,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    subject: str | int,
    scopes: list[str] | None = None,
    expires_minutes: int | None = None,
) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        {"scopes": scopes or []},
    )


def create_refresh_token(subject: str | int) -> tuple[str, str, datetime]:
    """Return ``(token, jti, expires_at)`` so the jti can be stored server side."""
    jti = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(subject),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": jti,
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, jti, expires_at


def create_reset_token(subject: str | int) -> str:
    return _create_token(
        subject, "reset", timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    )


def create_verify_token(subject: str | int) -> str:
    return _create_token(
        subject, "verify", timedelta(hours=settings.EMAIL_VERIFY_EXPIRE_HOURS)
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode a JWT, raising :class:`jwt.PyJWTError` when it is not usable."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"expected a {expected_type} token, got {payload.get('type')!r}"
        )
    return payload


def generate_api_key(prefix: str = "cj") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def constant_time_equals(left: str, right: str) -> bool:
    return secrets.compare_digest(left, right)
