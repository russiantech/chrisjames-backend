"""Payment, plan, subscription and advert schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import EmailStr, Field, computed_field

from app.models.enums import (
    AdPricingModel,
    AdStatus,
    PaymentPurpose,
    PaymentStatus,
)
from app.schemas.common import ORMSchema, Schema
from app.schemas.user import UserPublic


# --------------------------------------------------------------------- plans
class PlanRead(ORMSchema):
    id: int
    name: str
    slug: str
    description: str | None = None
    family: str
    amount_minor: int
    currency: str
    interval: str
    trial_days: int
    features: list[str] = Field(default_factory=list)
    entitlements: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    is_highlighted: bool
    badge: str | None = None
    position: int

    @computed_field
    @property
    def amount(self) -> float:
        return self.amount_minor / 100


class PlanWrite(Schema):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    slug: str | None = None
    description: str | None = None
    family: str = "engagement"
    amount_minor: Annotated[int, Field(ge=0)] = 0
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"
    interval: str = "one_time"
    trial_days: int = 0
    features: list[str] = Field(default_factory=list)
    entitlements: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_highlighted: bool = False
    badge: str | None = None
    position: int = 0


# ------------------------------------------------------------------ payments
class CheckoutCreate(Schema):
    """Start a payment. Either a plan or an explicit amount, not both."""

    plan_slug: str | None = None
    amount_minor: Annotated[int | None, Field(ge=100)] = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"
    purpose: PaymentPurpose = PaymentPurpose.OTHER
    description: Annotated[str | None, Field(max_length=300)] = None
    payer_email: EmailStr | None = None
    payer_name: Annotated[str | None, Field(max_length=160)] = None
    subject_type: Annotated[str | None, Field(max_length=40)] = None
    subject_id: int | None = None
    success_url: str | None = None
    cancel_url: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class CheckoutSession(Schema):
    reference: str
    checkout_url: str
    provider: str
    amount_minor: int
    currency: str
    expires_in: int = 3600


class PaymentRead(ORMSchema):
    id: int
    reference: str
    provider: str
    provider_reference: str | None = None
    amount_minor: int
    currency: str
    fee_minor: int
    refunded_minor: int
    status: str
    purpose: str
    description: str | None = None
    payer_email: str | None = None
    payer_name: str | None = None
    subject_type: str | None = None
    subject_id: int | None = None
    receipt_url: str | None = None
    paid_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime
    user: UserPublic | None = None
    plan: PlanRead | None = None

    @computed_field
    @property
    def amount(self) -> float:
        return self.amount_minor / 100


class RefundIn(Schema):
    amount_minor: Annotated[int | None, Field(gt=0)] = None
    reason: Annotated[str | None, Field(max_length=300)] = None


class SubscriptionRead(ORMSchema):
    id: int
    status: str
    started_at: datetime
    current_period_end: datetime | None = None
    cancel_at_period_end: bool
    plan: PlanRead


# ------------------------------------------------------------------- adverts
class AdSlotRead(ORMSchema):
    id: int
    key: str
    name: str
    description: str | None = None
    placement: str
    width: int | None = None
    height: int | None = None
    format: str
    pricing_model: str
    base_price_minor: int
    currency: str
    max_concurrent: int
    is_active: bool
    fallback_html: str | None = None


class AdSlotWrite(Schema):
    key: Annotated[str, Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_]+$")]
    name: Annotated[str, Field(max_length=120)]
    description: str | None = None
    placement: str = "sidebar"
    width: int | None = None
    height: int | None = None
    format: str = "fluid"
    pricing_model: AdPricingModel = AdPricingModel.FLAT_MONTHLY
    base_price_minor: Annotated[int, Field(ge=0)] = 0
    currency: str = "USD"
    max_concurrent: Annotated[int, Field(ge=1, le=10)] = 1
    is_active: bool = True
    fallback_html: str | None = None


class AdSlotUpdate(Schema):
    """Every field optional — for PATCH, where AdSlotWrite's required key/name
    would otherwise force every partial edit (e.g. a plain on/off toggle) to
    round-trip the whole slot."""

    name: Annotated[str | None, Field(max_length=120)] = None
    description: str | None = None
    placement: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    pricing_model: AdPricingModel | None = None
    base_price_minor: Annotated[int | None, Field(ge=0)] = None
    currency: str | None = None
    max_concurrent: Annotated[int | None, Field(ge=1, le=10)] = None
    is_active: bool | None = None
    fallback_html: str | None = None


class AdvertCreate(Schema):
    slot_id: int
    name: Annotated[str, Field(min_length=2, max_length=160)]
    creative_type: str = "image"
    headline: Annotated[str | None, Field(max_length=160)] = None
    body: Annotated[str | None, Field(max_length=500)] = None
    image_url: str | None = None
    media_id: int | None = None
    cta_label: Annotated[str | None, Field(max_length=60)] = None
    target_url: Annotated[str, Field(max_length=700)]
    accent: str = "primary"
    starts_on: datetime | None = None
    ends_on: datetime | None = None
    target_categories: list[str] = Field(default_factory=list)
    target_tags: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    target_devices: list[str] = Field(default_factory=list)


class AdvertUpdate(Schema):
    name: str | None = None
    headline: str | None = None
    body: str | None = None
    image_url: str | None = None
    cta_label: str | None = None
    target_url: str | None = None
    accent: str | None = None
    starts_on: datetime | None = None
    ends_on: datetime | None = None
    weight: Annotated[int | None, Field(ge=1, le=100)] = None
    impression_cap: int | None = None
    click_cap: int | None = None
    daily_impression_cap: int | None = None
    target_categories: list[str] | None = None
    target_tags: list[str] | None = None
    target_countries: list[str] | None = None
    target_devices: list[str] | None = None
    status: AdStatus | None = None


class AdvertRead(ORMSchema):
    id: int
    slot_id: int
    name: str
    creative_type: str
    headline: str | None = None
    body: str | None = None
    image_url: str | None = None
    cta_label: str | None = None
    target_url: str
    accent: str
    status: str
    starts_on: datetime | None = None
    ends_on: datetime | None = None
    weight: int
    impression_count: int
    click_count: int
    spend_minor: int
    rejection_reason: str | None = None
    created_at: datetime
    advertiser: UserPublic | None = None

    @computed_field
    @property
    def ctr(self) -> float:
        return self.click_count / self.impression_count if self.impression_count else 0.0


class AdCreativeServe(Schema):
    """The minimal payload the public site needs to render one advert."""

    id: int
    slot_key: str
    creative_type: str
    headline: str | None = None
    body: str | None = None
    image_url: str | None = None
    cta_label: str | None = None
    #: Click-through goes via the API so the click is counted.
    click_url: str
    html: str | None = None
    accent: str
    is_fallback: bool = False


class AdSlotServe(Schema):
    slot_key: str
    placement: str
    format: str
    width: int | None = None
    height: int | None = None
    creatives: list[AdCreativeServe] = Field(default_factory=list)
    fallback_html: str | None = None


class AdEventIn(Schema):
    advert_id: int
    type: str = "impression"
    post_id: int | None = None


class AdvertDecision(Schema):
    approve: bool
    reason: Annotated[str | None, Field(max_length=500)] = None
