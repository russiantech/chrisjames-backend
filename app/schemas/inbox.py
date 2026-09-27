"""Contact form, project brief and newsletter schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import EmailStr, Field, field_validator, model_validator

from app.models.enums import MessageStatus, RequestStatus, SubscriberStatus
from app.schemas.common import ORMSchema, Schema
from app.schemas.user import UserPublic


# ------------------------------------------------------------------- contact
class ContactCreate(Schema):
    name: Annotated[str, Field(min_length=2, max_length=160)]
    email: EmailStr
    phone: Annotated[str | None, Field(max_length=40)] = None
    company: Annotated[str | None, Field(max_length=160)] = None
    subject: Annotated[str, Field(min_length=3, max_length=240)]
    message: Annotated[str, Field(min_length=10, max_length=8000)]
    #: Honeypot field, hidden with CSS. Anything non-empty is treated as spam.
    website_url: str | None = None
    referrer: Annotated[str | None, Field(max_length=500)] = None


class ContactRead(ORMSchema):
    id: int
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    subject: str
    message: str
    status: str
    priority: str
    tags: list[str] = Field(default_factory=list)
    internal_note: str | None = None
    replied_at: datetime | None = None
    reply_body: str | None = None
    source: str
    spam_score: int
    created_at: datetime
    assigned_to: UserPublic | None = None


class ContactUpdate(Schema):
    status: MessageStatus | None = None
    priority: str | None = None
    tags: list[str] | None = None
    internal_note: str | None = None
    assigned_to_id: int | None = None


class ContactReply(Schema):
    subject: Annotated[str, Field(min_length=3, max_length=240)]
    body: Annotated[str, Field(min_length=5, max_length=20_000)]
    #: Copy the reply to the team inbox.
    cc_team: bool = False


# ------------------------------------------------------------------- requests
class ProjectRequestCreate(Schema):
    name: Annotated[str, Field(min_length=2, max_length=160)]
    email: EmailStr
    phone: Annotated[str | None, Field(max_length=40)] = None
    company: Annotated[str | None, Field(max_length=160)] = None
    company_size: Annotated[str | None, Field(max_length=40)] = None
    country: Annotated[str | None, Field(max_length=80)] = None
    website: Annotated[str | None, Field(max_length=255)] = None

    project_title: Annotated[str, Field(min_length=3, max_length=240)]
    summary: Annotated[str, Field(min_length=20, max_length=10_000)]
    service_types: Annotated[list[str], Field(max_length=12)] = Field(default_factory=list)
    tech_preferences: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list)
    attachment_ids: Annotated[list[int], Field(max_length=10)] = Field(default_factory=list)

    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD"
    timeline: Annotated[str | None, Field(max_length=40)] = None
    target_start: date | None = None
    engagement_model: Annotated[str | None, Field(max_length=40)] = None
    answers: dict[str, Any] = Field(default_factory=dict)

    website_url: str | None = None          # honeypot
    referrer: Annotated[str | None, Field(max_length=500)] = None
    utm: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _budget_order(self) -> "ProjectRequestCreate":
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("Minimum budget cannot exceed the maximum.")
        return self


class ProjectRequestRead(ORMSchema):
    id: int
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    company_size: str | None = None
    country: str | None = None
    website: str | None = None
    project_title: str
    summary: str
    service_types: list[str] = Field(default_factory=list)
    tech_preferences: list[str] = Field(default_factory=list)
    attachment_ids: list[int] = Field(default_factory=list)
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    currency: str
    timeline: str | None = None
    target_start: date | None = None
    engagement_model: str | None = None
    status: str
    lead_score: int
    quoted_amount: Decimal | None = None
    quote_sent_at: datetime | None = None
    internal_note: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)
    utm: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    assigned_to: UserPublic | None = None


class ProjectRequestUpdate(Schema):
    status: RequestStatus | None = None
    lead_score: Annotated[int | None, Field(ge=0, le=100)] = None
    assigned_to_id: int | None = None
    quoted_amount: Decimal | None = None
    internal_note: str | None = None


class ProjectRequestAck(Schema):
    """What the public form gets back — never the internal pipeline fields."""

    id: int
    reference: str
    message: str


# ----------------------------------------------------------------- newsletter
class SubscribeIn(Schema):
    email: EmailStr
    name: Annotated[str | None, Field(max_length=160)] = None
    topics: Annotated[list[str], Field(max_length=20)] = Field(default_factory=list)
    source: Annotated[str, Field(max_length=40)] = "footer_form"
    website_url: str | None = None          # honeypot


class SubscriberRead(ORMSchema):
    id: int
    email: EmailStr
    name: str | None = None
    status: str
    topics: list[str] = Field(default_factory=list)
    confirmed_at: datetime | None = None
    source: str
    created_at: datetime


class CampaignCreate(Schema):
    subject: Annotated[str, Field(min_length=3, max_length=240)]
    preheader: Annotated[str | None, Field(max_length=240)] = None
    body_html: str = ""
    post_id: int | None = None
    topics: list[str] = Field(default_factory=list)
    scheduled_for: datetime | None = None
    is_test: bool = False

    @field_validator("body_html")
    @classmethod
    def _needs_content(cls, value: str) -> str:
        return value


class CampaignRead(ORMSchema):
    id: int
    subject: str
    preheader: str | None = None
    status: str
    post_id: int | None = None
    topics: list[str] = Field(default_factory=list)
    scheduled_for: datetime | None = None
    sent_at: datetime | None = None
    recipient_count: int
    open_count: int
    click_count: int
    created_at: datetime
