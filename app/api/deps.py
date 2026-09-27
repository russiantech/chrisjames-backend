"""Shared route dependencies: the session, the caller, and permission gates."""

from __future__ import annotations

from typing import Annotated, Callable

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotAuthenticated, PermissionDenied
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserStatus
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services.comments import anon_key

#: ``auto_error=False`` so anonymous access can fall through to ``None``.
bearer = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


async def _load_user(db: AsyncSession, user_id: str | int) -> User | None:
    return await db.scalar(
        select(User)
        .where(User.id == int(user_id))
        .options(selectinload(User.roles))
    )


async def get_current_user_optional(db: DbSession, creds: Credentials) -> User | None:
    """The caller, or ``None``. Never raises — used by public endpoints."""
    if creds is None or not creds.credentials:
        return None
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        return None
    user = await _load_user(db, payload.get("sub", 0))
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(db: DbSession, creds: Credentials) -> User:
    if creds is None or not creds.credentials:
        raise NotAuthenticated()
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.ExpiredSignatureError as exc:
        raise NotAuthenticated("Your session expired. Sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise NotAuthenticated("That token is not valid.") from exc

    user = await _load_user(db, payload.get("sub", 0))
    if user is None:
        raise NotAuthenticated("That account no longer exists.")
    if user.status == UserStatus.SUSPENDED:
        raise PermissionDenied("This account is suspended.")
    if not user.is_active:
        raise PermissionDenied("Confirm your e-mail address to continue.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
MaybeUser = Annotated[User | None, Depends(get_current_user_optional)]


def require(*permissions: str, mode: str = "any") -> Callable:
    """Dependency factory gating a route behind one or more permissions.

    ``mode="any"`` passes when the caller holds at least one; ``mode="all"``
    demands every one.
    """

    async def guard(user: CurrentUser) -> User:
        check = user.has_any(*permissions) if mode == "any" else all(
            user.has_permission(p) for p in permissions
        )
        if not check:
            joiner = " or " if mode == "any" else " and "
            raise PermissionDenied(
                "This needs the " + joiner.join(permissions) + " permission."
            )
        return user

    return Depends(guard)


async def pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, alias="perPage")] = 20,
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)


Pagination = Annotated[PaginationParams, Depends(pagination)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def request_anon_key(request: Request) -> str:
    """Stable pseudonymous id for a signed-out reader."""
    return anon_key(client_ip(request), request.headers.get("user-agent"))


AnonKey = Annotated[str, Depends(request_anon_key)]


def request_device(request: Request) -> str:
    agent = (request.headers.get("user-agent") or "").lower()
    if "mobile" in agent or "android" in agent or "iphone" in agent:
        return "mobile"
    if "tablet" in agent or "ipad" in agent:
        return "tablet"
    return "desktop"


def request_country(request: Request) -> str | None:
    # Populated by Cloudflare, Vercel and most CDNs.
    return (
        request.headers.get("cf-ipcountry")
        or request.headers.get("x-vercel-ip-country")
    )
