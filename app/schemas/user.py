"""Authentication, account and role schemas."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import EmailStr, Field, field_validator

from app.models.enums import UserStatus
from app.schemas.common import ORMSchema, Schema

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")

Password = Annotated[str, Field(min_length=5, max_length=128)]


def _check_password_strength(value: str) -> str:
    checks = (
        (any(c.islower() for c in value), "a lowercase letter"),
        (any(c.isupper() for c in value), "an uppercase letter"),
        (any(c.isdigit() for c in value), "a number"),
    )
    missing = [label for ok, label in checks if not ok]
    if missing:
        raise ValueError("Password needs " + ", ".join(missing) + ".")
    return value


# --------------------------------------------------------------------- roles
class RoleBase(Schema):
    name: Annotated[str, Field(min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")]
    label: Annotated[str, Field(min_length=2, max_length=80)]
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    is_superuser: bool = False
    priority: int = 0


class RoleCreate(RoleBase):
    pass


class RoleUpdate(Schema):
    label: str | None = None
    description: str | None = None
    permissions: list[str] | None = None
    priority: int | None = None


class RoleRead(ORMSchema):
    id: int
    name: str
    label: str
    description: str | None
    permissions: list[str]
    is_superuser: bool
    is_system: bool
    priority: int


class RoleSummary(ORMSchema):
    id: int
    name: str
    label: str


class PermissionInfo(Schema):
    name: str
    description: str
    group: str


# --------------------------------------------------------------------- users
class UserPublic(ORMSchema):
    """Safe to show to anyone — used for bylines and comment authors."""

    id: int
    username: str
    full_name: str | None = None
    display_name: str
    headline: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    website: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)


class UserRead(UserPublic):
    email: EmailStr
    status: str
    location: str | None = None
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    roles: list[RoleSummary] = Field(default_factory=list)


class UserMe(UserRead):
    """The signed-in account, including its effective permission set.

    ``permissions`` and ``is_superuser`` are computed properties on the ORM
    model; ``from_attributes`` reads them like any other field.
    """

    permissions: list[str] = Field(default_factory=list)
    is_superuser: bool = False


class UserCreate(Schema):
    email: EmailStr
    username: Annotated[str, Field(min_length=3, max_length=30)]
    password: Password
    full_name: str | None = None

    @field_validator("username")
    @classmethod
    def _valid_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not USERNAME_RE.match(value):
            raise ValueError(
                "Username must be 3–30 characters: lowercase letters, numbers, "
                "dots, dashes or underscores, starting with a letter or number."
            )
        return value

    @field_validator("password")
    @classmethod
    def _strong(cls, value: str) -> str:
        return _check_password_strength(value)


class UserRegister(UserCreate):
    accept_terms: bool = True
    subscribe_newsletter: bool = False


class UserAdminCreate(UserCreate):
    role_names: list[str] = Field(default_factory=lambda: ["member"])
    status: UserStatus = UserStatus.ACTIVE
    send_invite_email: bool = True


class UserUpdate(Schema):
    full_name: str | None = None
    headline: Annotated[str | None, Field(max_length=160)] = None
    bio: str | None = None
    avatar_url: str | None = None
    website: str | None = None
    location: str | None = None
    social_links: dict[str, str] | None = None


class UserAdminUpdate(UserUpdate):
    status: UserStatus | None = None
    role_names: list[str] | None = None
    extra_permissions: list[str] | None = None
    denied_permissions: list[str] | None = None


class PasswordChange(Schema):
    current_password: str
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def _strong(cls, value: str) -> str:
        return _check_password_strength(value)


class PasswordResetRequest(Schema):
    email: EmailStr


class PasswordResetConfirm(Schema):
    token: str
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def _strong(cls, value: str) -> str:
        return _check_password_strength(value)


# -------------------------------------------------------------------- tokens
class LoginRequest(Schema):
    #: Either the e-mail address or the username.
    identifier: str
    password: str
    remember_me: bool = False


class TokenPair(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(Schema):
    refresh_token: str


class SessionRead(ORMSchema):
    id: int
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None
    ip_address: str | None


class EmailVerifyRequest(Schema):
    token: str
