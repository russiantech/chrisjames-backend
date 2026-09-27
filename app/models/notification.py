"""In-app notifications, per-channel preferences and the outbound e-mail log."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, TimestampMixin
from app.models.enums import NotificationChannel, NotificationKind

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base, PKMixin, TimestampMixin):
    """One row per recipient per event. Streamed to the client over SSE."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_inbox", "recipient_id", "read_at", "created_at"),
    )

    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(40), default=NotificationKind.SYSTEM)

    title: Mapped[str] = mapped_column(String(220))
    body: Mapped[str | None] = mapped_column(Text)
    #: Where clicking the notification takes the reader.
    url: Mapped[str | None] = mapped_column(String(500))
    icon: Mapped[str | None] = mapped_column(String(60))
    accent: Mapped[str] = mapped_column(String(24), default="primary")

    # loose polymorphic pointer to whatever triggered it
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Collapses duplicates, e.g. "5 people reacted to your post".
    group_key: Mapped[str | None] = mapped_column(String(120), index=True)
    group_count: Mapped[int] = mapped_column(Integer, default=1)

    recipient: Mapped["User"] = relationship(
        back_populates="notifications", foreign_keys=[recipient_id]
    )
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id], lazy="joined")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationPreference(Base, PKMixin, TimestampMixin):
    """Per-user, per-kind, per-channel opt in/out."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "channel", name="uq_notification_pref"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default=NotificationKind.SYSTEM)
    channel: Mapped[str] = mapped_column(
        String(20), default=NotificationChannel.IN_APP
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    #: ``instant`` | ``hourly`` | ``daily`` | ``weekly``
    digest: Mapped[str] = mapped_column(String(20), default="instant")

    user: Mapped["User"] = relationship(back_populates="notification_preferences")


class WebhookEndpoint(Base, PKMixin, TimestampMixin):
    """Outbound webhook, so events can drive Slack, Discord or a custom service."""

    __tablename__ = "webhook_endpoints"

    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(700))
    secret: Mapped[str] = mapped_column(String(120))
    #: Notification kinds this endpoint subscribes to; empty means all.
    kinds: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailLog(Base, PKMixin, TimestampMixin):
    """Every outbound e-mail, whether sent or captured in dry-run mode."""

    __tablename__ = "email_logs"

    to_address: Mapped[str] = mapped_column(String(255), index=True)
    from_address: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(300))
    template: Mapped[str | None] = mapped_column(String(80))
    body_html: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: ``queued`` | ``sent`` | ``failed`` | ``dry_run``
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
