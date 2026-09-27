"""Registration, sign-in, token refresh, verification and password reset."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, client_ip
from app.core.config import settings
from app.core.exceptions import Conflict, NotAuthenticated, NotFound, ValidationFailed
from app.core.permissions import DEFAULT_SIGNUP_ROLE
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    create_verify_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserStatus
from app.models.inbox import NewsletterSubscriber
from app.models.user import RefreshToken, Role, User
from app.schemas.common import Message
from app.schemas.user import (
    EmailVerifyRequest,
    LoginRequest,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    SessionRead,
    TokenPair,
    UserMe,
    UserRegister,
)
from app.services.email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_LOGINS = 8
LOCKOUT_MINUTES = 15


async def _issue_tokens(
    db: DbSession, user: User, request: Request
) -> TokenPair:
    access = create_access_token(user.id, scopes=sorted(user.permissions))
    refresh, jti, expires_at = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            user_agent=(request.headers.get("user-agent") or "")[:300],
            ip_address=client_ip(request),
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    await db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserMe, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: DbSession) -> User:
    """Create an account. New accounts start as ``member``."""
    clash = await db.scalar(
        select(User).where(
            or_(User.email == payload.email.lower(), User.username == payload.username)
        )
    )
    if clash is not None:
        field = "e-mail address" if clash.email == payload.email.lower() else "username"
        raise Conflict(f"That {field} is already in use.")

    role = await db.scalar(select(Role).where(Role.name == DEFAULT_SIGNUP_ROLE))
    user = User(
        email=payload.email.lower(),
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        status=UserStatus.PENDING,
    )
    if role is not None:
        user.roles.append(role)
    db.add(user)
    await db.flush()

    if payload.subscribe_newsletter:
        import secrets

        db.add(
            NewsletterSubscriber(
                email=user.email,
                name=user.full_name,
                user_id=user.id,
                source="registration",
                unsubscribe_token=secrets.token_urlsafe(24),
            )
        )

    await send_email(
        db,
        to_address=user.email,
        template="verify_email",
        context={
            "name": user.display_name,
            "action_url": f"{settings.SITE_URL}/verify?token={create_verify_token(user.id)}",
        },
    )
    await db.commit()
    await db.refresh(user, ["roles"])
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    identifier = payload.identifier.strip().lower()
    user = await db.scalar(
        select(User)
        .where(or_(User.email == identifier, User.username == identifier))
        .options(selectinload(User.roles))
    )

    now = datetime.now(timezone.utc)
    if user is not None and user.locked_until and user.locked_until > now:
        raise NotAuthenticated(
            "Too many failed attempts. Try again in a few minutes."
        )

    if user is None or not verify_password(payload.password, user.hashed_password or ""):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_count = 0
            await db.commit()
        # One message for both cases, so the form cannot enumerate accounts.
        raise NotAuthenticated("That e-mail or password is not right.")

    if user.status == UserStatus.SUSPENDED:
        raise NotAuthenticated("This account is suspended. Contact the site owner.")
    if user.status == UserStatus.PENDING:
        raise NotAuthenticated("Confirm your e-mail address first. Check your inbox.")

    user.locked_until = None
    return await _issue_tokens(db, user, request)


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(
    payload: RefreshRequest, request: Request, db: DbSession
) -> TokenPair:
    """Exchange a refresh token. The old one is revoked — tokens rotate."""
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except jwt.PyJWTError as exc:
        raise NotAuthenticated("That refresh token is not valid.") from exc

    record = await db.scalar(
        select(RefreshToken).where(RefreshToken.jti == claims.get("jti", ""))
    )
    if record is None or record.revoked_at is not None:
        raise NotAuthenticated("That session has already ended.")

    user = await db.scalar(
        select(User).where(User.id == record.user_id).options(selectinload(User.roles))
    )
    if user is None or not user.is_active:
        raise NotAuthenticated("That account is no longer active.")

    record.revoked_at = datetime.now(timezone.utc)
    return await _issue_tokens(db, user, request)


@router.post("/logout", response_model=Message)
async def logout(payload: RefreshRequest, db: DbSession) -> Message:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except jwt.PyJWTError:
        return Message(detail="Signed out.")
    record = await db.scalar(
        select(RefreshToken).where(RefreshToken.jti == claims.get("jti", ""))
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return Message(detail="Signed out.")


@router.get("/me", response_model=UserMe)
async def read_me(user: CurrentUser) -> User:
    return user


@router.get("/sessions", response_model=list[SessionRead])
async def list_sessions(user: CurrentUser, db: DbSession) -> list[RefreshToken]:
    rows = await db.scalars(
        select(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .order_by(RefreshToken.created_at.desc())
        .limit(50)
    )
    return list(rows.all())


@router.delete("/sessions/{session_id}", response_model=Message)
async def revoke_session(session_id: int, user: CurrentUser, db: DbSession) -> Message:
    record = await db.get(RefreshToken, session_id)
    if record is None or record.user_id != user.id:
        raise NotFound("No such session.")
    record.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return Message(detail="Session ended.")


@router.post("/verify-email", response_model=Message)
async def verify_email(payload: EmailVerifyRequest, db: DbSession) -> Message:
    try:
        claims = decode_token(payload.token, "verify")
    except jwt.PyJWTError as exc:
        raise ValidationFailed("That confirmation link expired. Ask for a new one.") from exc

    user = await db.get(User, int(claims["sub"]))
    if user is None:
        raise NotFound("That account no longer exists.")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        user.status = UserStatus.ACTIVE
        await send_email(
            db,
            to_address=user.email,
            template="welcome",
            context={"name": user.display_name, "action_url": settings.SITE_URL},
        )
        await db.commit()
    return Message(detail="E-mail confirmed. You can sign in now.")


@router.post("/password/forgot", response_model=Message)
async def forgot_password(payload: PasswordResetRequest, db: DbSession) -> Message:
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is not None:
        await send_email(
            db,
            to_address=user.email,
            template="reset_password",
            context={
                "name": user.display_name,
                "minutes": settings.PASSWORD_RESET_EXPIRE_MINUTES,
                "action_url": f"{settings.SITE_URL}/reset?token={create_reset_token(user.id)}",
            },
        )
        await db.commit()
    # Same reply either way, so the form cannot be used to test addresses.
    return Message(detail="If that address has an account, a reset link is on its way.")


@router.post("/password/reset", response_model=Message)
async def reset_password(payload: PasswordResetConfirm, db: DbSession) -> Message:
    try:
        claims = decode_token(payload.token, "reset")
    except jwt.PyJWTError as exc:
        raise ValidationFailed("That reset link expired. Ask for a new one.") from exc

    user = await db.get(User, int(claims["sub"]))
    if user is None:
        raise NotFound("That account no longer exists.")

    user.hashed_password = hash_password(payload.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    # Every existing session dies with the old password.
    for token in await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ):
        token.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return Message(detail="Password changed. Sign in with the new one.")


@router.post("/password/change", response_model=Message)
async def change_password(
    payload: PasswordChange, user: CurrentUser, db: DbSession
) -> Message:
    if not verify_password(payload.current_password, user.hashed_password or ""):
        raise ValidationFailed("Your current password is not right.")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return Message(detail="Password changed.")
