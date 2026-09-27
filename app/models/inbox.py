"""Everything that arrives from the public site: contact, briefs, newsletter."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.enums import MessageStatus, RequestStatus, SubscriberStatus

if TYPE_CHECKING:
    from app.models.user import User


class ContactMessage(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    """A note from the contact form."""

    __tablename__ = "contact_messages"

    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    company: Mapped[str | None] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(240))
    message: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20), default=MessageStatus.UNREAD, index=True
    )
    #: ``low`` | ``normal`` | ``high``
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    internal_note: Mapped[str | None] = mapped_column(Text)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_body: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(40), default="contact_form")
    referrer: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    spam_score: Mapped[int] = mapped_column(Integer, default=0)

    assigned_to: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_to_id], lazy="selectin"
    )


class ProjectRequest(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    """A qualified brief from the "Get started" modal — the sales pipeline."""

    __tablename__ = "project_requests"

    # who -----------------------------------------------------------------
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    company: Mapped[str | None] = mapped_column(String(160))
    company_size: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(String(255))

    # what ----------------------------------------------------------------
    project_title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text)
    #: e.g. ``["web app", "ai", "automation"]``
    service_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    tech_preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: Media asset ids for briefs, wireframes and specs.
    attachment_ids: Mapped[list[int]] = mapped_column(JSON, default=list)

    # commercials ---------------------------------------------------------
    budget_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    budget_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    #: ``asap`` | ``1_month`` | ``1_quarter`` | ``flexible``
    timeline: Mapped[str | None] = mapped_column(String(40))
    target_start: Mapped[date | None] = mapped_column(Date)
    engagement_model: Mapped[str | None] = mapped_column(String(40))

    # pipeline ------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(20), default=RequestStatus.NEW, index=True
    )
    #: 0–100, set during triage.
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    quoted_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    quote_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    internal_note: Mapped[str | None] = mapped_column(Text)
    #: Free-form answers to whatever extra questions the form asked.
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    referrer: Mapped[str | None] = mapped_column(String(500))
    utm: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))

    assigned_to: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_to_id], lazy="selectin"
    )


class NewsletterSubscriber(Base, PKMixin, TimestampMixin):
    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(
        String(20), default=SubscriberStatus.PENDING, index=True
    )
    #: Category slugs the reader asked for; empty means everything.
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    confirm_token: Mapped[str | None] = mapped_column(String(64), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribe_token: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(40), default="footer_form")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class NewsletterCampaign(Base, PKMixin, TimestampMixin):
    __tablename__ = "newsletter_campaigns"

    subject: Mapped[str] = mapped_column(String(240))
    preheader: Mapped[str | None] = mapped_column(String(240))
    body_html: Mapped[str] = mapped_column(Text, default="")
    #: Optional: build the body from a published post.
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL")
    )
    #: ``draft`` | ``scheduled`` | ``sending`` | ``sent`` | ``failed``
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
