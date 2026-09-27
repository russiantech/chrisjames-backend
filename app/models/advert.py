"""Advert inventory: slots on the page, creatives booked into them, and stats."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, TimestampMixin
from app.models.enums import AdPricingModel, AdStatus

if TYPE_CHECKING:
    from app.models.user import User


class AdSlot(Base, PKMixin, TimestampMixin):
    """A named position on the site that can hold one or more creatives."""

    __tablename__ = "ad_slots"

    #: Referenced from the client and from ``ad_slot`` content blocks.
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    #: ``header`` | ``sidebar`` | ``in_article`` | ``footer`` | ``feed`` | ``modal``
    placement: Mapped[str] = mapped_column(String(30), default="sidebar", index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    #: ``728x90``, ``300x250``, ``fluid`` …
    format: Mapped[str] = mapped_column(String(30), default="fluid")

    pricing_model: Mapped[str] = mapped_column(
        String(20), default=AdPricingModel.FLAT_MONTHLY
    )
    base_price_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    #: How many creatives may rotate in this slot at once.
    max_concurrent: Mapped[int] = mapped_column(Integer, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Shown when nothing is booked, e.g. a "your ad here" card.
    fallback_html: Mapped[str | None] = mapped_column(Text)

    adverts: Mapped[list["Advert"]] = relationship(back_populates="slot")


class Advert(Base, PKMixin, TimestampMixin):
    """One booked creative."""

    __tablename__ = "adverts"
    __table_args__ = (
        Index("ix_advert_serving", "slot_id", "status", "starts_on", "ends_on"),
    )

    slot_id: Mapped[int] = mapped_column(
        ForeignKey("ad_slots.id", ondelete="CASCADE"), index=True
    )
    advertiser_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL")
    )

    # creative ------------------------------------------------------------
    name: Mapped[str] = mapped_column(String(160))
    #: ``image`` | ``html`` | ``native`` | ``video`` | ``script``
    creative_type: Mapped[str] = mapped_column(String(20), default="image")
    headline: Mapped[str | None] = mapped_column(String(160))
    body: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(700))
    media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    cta_label: Mapped[str | None] = mapped_column(String(60))
    target_url: Mapped[str] = mapped_column(String(700))
    #: Sanitised markup for ``html`` creatives; admin-authored only.
    html: Mapped[str | None] = mapped_column(Text)
    #: Brand colour token so native ads sit inside the theme.
    accent: Mapped[str] = mapped_column(String(24), default="primary")

    # booking -------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(24), default=AdStatus.DRAFT, index=True
    )
    starts_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Higher weight wins more of the rotation.
    weight: Mapped[int] = mapped_column(Integer, default=1)
    #: Stop serving after this many impressions; ``0`` means unlimited.
    impression_cap: Mapped[int] = mapped_column(Integer, default=0)
    click_cap: Mapped[int] = mapped_column(Integer, default=0)
    daily_impression_cap: Mapped[int] = mapped_column(Integer, default=0)

    # targeting -----------------------------------------------------------
    #: Empty list means "everywhere".
    target_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_devices: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclude_post_ids: Mapped[list[int]] = mapped_column(JSON, default=list)

    # review --------------------------------------------------------------
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # metrics -------------------------------------------------------------
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    spend_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    slot: Mapped[AdSlot] = relationship(back_populates="adverts")
    advertiser: Mapped["User | None"] = relationship(
        back_populates="adverts", foreign_keys=[advertiser_id], lazy="selectin"
    )

    @property
    def ctr(self) -> float:
        return (self.click_count / self.impression_count) if self.impression_count else 0.0


class AdEvent(Base, PKMixin, TimestampMixin):
    """Impression or click. Rolled up nightly into the counters on ``Advert``."""

    __tablename__ = "ad_events"
    __table_args__ = (Index("ix_ad_event_advert_day", "advert_id", "day"),)

    advert_id: Mapped[int] = mapped_column(
        ForeignKey("adverts.id", ondelete="CASCADE"), index=True
    )
    #: ``impression`` | ``click`` | ``close``
    type: Mapped[str] = mapped_column(String(16), index=True)
    day: Mapped[datetime | None] = mapped_column(Date, index=True)
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL")
    )
    anon_key: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(2))
    device: Mapped[str | None] = mapped_column(String(20))
    referrer: Mapped[str | None] = mapped_column(String(500))
    revenue_minor: Mapped[int] = mapped_column(BigInteger, default=0)


class Sponsor(Base, PKMixin, TimestampMixin):
    """Logos on the "trusted by" rail, separate from paid rotation."""

    __tablename__ = "sponsors"

    name: Mapped[str] = mapped_column(String(120))
    logo_url: Mapped[str] = mapped_column(String(700))
    website: Mapped[str | None] = mapped_column(String(500))
    tier: Mapped[str] = mapped_column(String(20), default="partner")
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Optional greyscale opacity, matching the existing logo rail.
    opacity: Mapped[float] = mapped_column(Float, default=0.6)
