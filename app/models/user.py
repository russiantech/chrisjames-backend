"""Accounts, roles and session tokens."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.enums import UserStatus

if TYPE_CHECKING:
    from app.models.advert import Advert
    from app.models.comment import Comment
    from app.models.media import MediaAsset
    from app.models.notification import Notification, NotificationPreference
    from app.models.payment import Payment
    from app.models.post import Post


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("granted_at", DateTime(timezone=True), nullable=True),
    Column("granted_by_id", ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
)


class Role(Base, PKMixin, TimestampMixin):
    """A named bundle of permissions.

    Permissions live in a JSON array rather than a join table so an
    administrator can mint a bespoke role from the dashboard without a schema
    migration. The catalogue of valid strings is in ``app.core.permissions``.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Higher priority wins when two roles disagree; also drives display order.
    priority: Mapped[int] = mapped_column(Integer, default=0)

    users: Mapped[list["User"]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        primaryjoin="Role.id == user_roles.c.role_id",
        secondaryjoin="User.id == user_roles.c.user_id",
        lazy="selectin",
    )

    def has(self, permission: str) -> bool:
        return self.is_superuser or permission in (self.permissions or [])


class User(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    # identity ----------------------------------------------------------
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(20), default=UserStatus.PENDING, index=True
    )

    # profile -----------------------------------------------------------
    headline: Mapped[str | None] = mapped_column(String(160))
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(120))
    #: ``{"github": "...", "linkedin": "...", "x": "..."}``
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)

    # flags -------------------------------------------------------------
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Individual grants layered on top of the user's roles.
    extra_permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: Permissions explicitly revoked even if a role grants them.
    denied_permissions: Mapped[list[str]] = mapped_column(JSON, default=list)

    # relationships -----------------------------------------------------
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        primaryjoin="User.id == user_roles.c.user_id",
        secondaryjoin="Role.id == user_roles.c.role_id",
        lazy="selectin",
    )
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        foreign_keys="Post.author_id",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="author",
        foreign_keys="Comment.author_id",
        cascade="all, delete-orphan",
    )
    media: Mapped[list["MediaAsset"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="recipient",
        foreign_keys="Notification.recipient_id",
        cascade="all, delete-orphan",
    )
    notification_preferences: Mapped[list["NotificationPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user", foreign_keys="Payment.user_id"
    )
    adverts: Mapped[list["Advert"]] = relationship(
        back_populates="advertiser", foreign_keys="Advert.advertiser_id"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # helpers -----------------------------------------------------------
    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None

    @property
    def is_superuser(self) -> bool:
        return any(role.is_superuser for role in self.roles)

    @property
    def role_names(self) -> list[str]:
        return sorted(role.name for role in self.roles)

    @property
    def permissions(self) -> set[str]:
        granted: set[str] = set(self.extra_permissions or [])
        for role in self.roles:
            granted.update(role.permissions or [])
        return granted - set(self.denied_permissions or [])

    def has_permission(self, permission: str) -> bool:
        if permission in set(self.denied_permissions or []):
            return False
        return self.is_superuser or permission in self.permissions

    def has_any(self, *permissions: str) -> bool:
        return any(self.has_permission(p) for p in permissions)

    @property
    def display_name(self) -> str:
        return self.full_name or self.username


class RefreshToken(Base, PKMixin, TimestampMixin):
    """Server-side record of an issued refresh token, so it can be revoked."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("jti", name="uq_refresh_token_jti"),
        Index("ix_refresh_token_user_active", "user_id", "revoked_at"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    jti: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip_address: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
