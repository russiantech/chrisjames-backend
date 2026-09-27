"""Notification, preference and e-mail schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field

from app.models.enums import NotificationChannel, NotificationKind
from app.schemas.common import ORMSchema, Schema
from app.schemas.user import UserPublic


class NotificationRead(ORMSchema):
    id: int
    kind: str
    title: str
    body: str | None = None
    url: str | None = None
    icon: str | None = None
    accent: str
    subject_type: str | None = None
    subject_id: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    seen_at: datetime | None = None
    group_count: int
    created_at: datetime
    actor: UserPublic | None = None

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationCounts(Schema):
    unread: int = 0
    unseen: int = 0
    total: int = 0
    #: Unread split by kind, so the UI can badge each inbox tab.
    by_kind: dict[str, int] = Field(default_factory=dict)


class NotificationMarkIn(Schema):
    #: Empty list means "everything currently unread".
    ids: list[int] = Field(default_factory=list)
    read: bool = True


class PreferenceIn(Schema):
    kind: NotificationKind
    channel: NotificationChannel
    enabled: bool = True
    digest: str = "instant"


class PreferenceRead(ORMSchema):
    id: int
    kind: str
    channel: str
    enabled: bool
    digest: str


class PreferenceBulkIn(Schema):
    preferences: Annotated[list[PreferenceIn], Field(max_length=200)]


class WebhookEndpointIn(Schema):
    label: Annotated[str, Field(max_length=120)]
    url: Annotated[str, Field(max_length=700)]
    kinds: list[NotificationKind] = Field(default_factory=list)
    is_active: bool = True


class WebhookEndpointRead(ORMSchema):
    id: int
    label: str
    url: str
    kinds: list[str] = Field(default_factory=list)
    is_active: bool
    failure_count: int
    last_delivery_at: datetime | None = None


class EmailLogRead(ORMSchema):
    id: int
    to_address: str
    subject: str
    template: str | None = None
    status: str
    error: str | None = None
    attempts: int
    sent_at: datetime | None = None
    created_at: datetime
