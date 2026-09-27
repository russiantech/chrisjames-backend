"""Payments, plans and subscriptions.

Amounts are stored as integer minor units (cents/kobo) to keep arithmetic
exact; the API converts to a decimal string on the way out.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
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
from app.models.enums import PaymentPurpose, PaymentStatus

if TYPE_CHECKING:
    from app.models.user import User


class Plan(Base, PKMixin, TimestampMixin):
    """A purchasable package: an engagement tier or an advert bundle."""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    #: ``engagement`` | ``advert`` | ``membership``
    family: Mapped[str] = mapped_column(String(30), default="engagement", index=True)

    amount_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    #: ``one_time`` | ``monthly`` | ``yearly``
    interval: Mapped[str] = mapped_column(String(20), default="one_time")
    trial_days: Mapped[int] = mapped_column(Integer, default=0)

    #: Bullet list rendered on the pricing card.
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: Machine-readable entitlements, e.g. ``{"ad_slots": 3, "support": "24h"}``.
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_highlighted: Mapped[bool] = mapped_column(Boolean, default=False)
    badge: Mapped[str | None] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0)
    provider_price_id: Mapped[str | None] = mapped_column(String(120))


class Payment(Base, PKMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_reference", name="uq_payment_provider_ref"),
        Index("ix_payment_status_created", "status", "created_at"),
    )

    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(20), default="mock")
    provider_reference: Mapped[str | None] = mapped_column(String(160), index=True)

    amount_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    fee_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    refunded_minor: Mapped[int] = mapped_column(BigInteger, default=0)

    status: Mapped[str] = mapped_column(
        String(24), default=PaymentStatus.PENDING, index=True
    )
    purpose: Mapped[str] = mapped_column(
        String(24), default=PaymentPurpose.OTHER, index=True
    )
    description: Mapped[str | None] = mapped_column(String(300))

    # payer ---------------------------------------------------------------
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    payer_email: Mapped[str | None] = mapped_column(String(255), index=True)
    payer_name: Mapped[str | None] = mapped_column(String(160))

    # what it paid for ----------------------------------------------------
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL")
    )
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[int | None] = mapped_column(Integer)

    checkout_url: Mapped[str | None] = mapped_column(String(700))
    receipt_url: Mapped[str | None] = mapped_column(String(700))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    #: Raw provider payload, retained for reconciliation.
    provider_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Both are serialised on every read, so they load with the payment.
    user: Mapped["User | None"] = relationship(
        back_populates="payments", foreign_keys=[user_id], lazy="selectin"
    )
    plan: Mapped[Plan | None] = relationship(lazy="selectin")

    @property
    def amount(self) -> float:
        return self.amount_minor / 100

    @property
    def is_settled(self) -> bool:
        return self.status == PaymentStatus.SUCCEEDED


class Subscription(Base, PKMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    #: ``trialing`` | ``active`` | ``past_due`` | ``cancelled`` | ``expired``
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_reference: Mapped[str | None] = mapped_column(String(160))

    plan: Mapped[Plan] = relationship(lazy="joined")


class WebhookEvent(Base, PKMixin, TimestampMixin):
    """Inbound provider webhooks, stored so delivery is idempotent."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_event"),
    )

    provider: Mapped[str] = mapped_column(String(20), index=True)
    event_id: Mapped[str] = mapped_column(String(160), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
