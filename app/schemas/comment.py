"""Comment, reply, reaction and report schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import EmailStr, Field, field_validator

from app.models.enums import ModerationState, ReactionType
from app.schemas.common import ORMSchema, Schema
from app.schemas.user import UserPublic


class CommentCreate(Schema):
    #: Markdown. Fenced code blocks are preserved and highlighted on render.
    body: Annotated[str, Field(min_length=1, max_length=10_000)]
    parent_id: int | None = None
    #: Required only when the commenter is not signed in.
    guest_name: Annotated[str | None, Field(max_length=120)] = None
    guest_email: EmailStr | None = None
    guest_website: Annotated[str | None, Field(max_length=255)] = None
    #: Honeypot. Bots fill it; real browsers never see it.
    website_url: str | None = None

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Write something before posting.")
        return value.strip()


class CommentUpdate(Schema):
    body: Annotated[str, Field(min_length=1, max_length=10_000)]


class CommentRead(ORMSchema):
    id: int
    post_id: int
    parent_id: int | None = None
    depth: int
    path: str
    body: str
    body_html: str
    display_name: str
    author: UserPublic | None = None
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    is_pinned: bool
    is_author_reply: bool
    moderation_state: str
    reply_count: int
    reaction_count: int
    mentions: list[str] = Field(default_factory=list)
    #: Populated when the tree is requested nested rather than flat.
    replies: list["CommentRead"] = Field(default_factory=list)
    my_reaction: str | None = None
    can_edit: bool = False
    can_delete: bool = False
    can_moderate: bool = False


class CommentModerationIn(Schema):
    state: ModerationState
    note: Annotated[str | None, Field(max_length=300)] = None
    #: Apply the same decision to every reply beneath this comment.
    cascade: bool = False


class CommentReactionIn(Schema):
    type: ReactionType = ReactionType.LIKE


class CommentReportIn(Schema):
    reason: Annotated[str, Field(max_length=40)]
    detail: Annotated[str | None, Field(max_length=1000)] = None

    @field_validator("reason")
    @classmethod
    def _known_reason(cls, value: str) -> str:
        allowed = {"spam", "abuse", "off_topic", "misinformation", "illegal", "other"}
        if value not in allowed:
            raise ValueError(f"Reason must be one of: {', '.join(sorted(allowed))}.")
        return value


class CommentPin(Schema):
    pinned: bool = True


CommentRead.model_rebuild()
