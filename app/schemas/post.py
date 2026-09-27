"""Blog post, content block and taxonomy schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import EmailStr, Field, field_validator, model_validator

from app.models.enums import BlockType, PostStatus, PostVisibility, ReactionType
from app.schemas.common import ORMSchema, Schema
from app.schemas.user import UserPublic


# ------------------------------------------------------------------ taxonomy
class CategoryBase(Schema):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    slug: str | None = None
    description: str | None = None
    icon: str | None = None
    accent: str = "primary"
    parent_id: int | None = None
    position: int = 0
    is_visible: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(Schema):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    accent: str | None = None
    parent_id: int | None = None
    position: int | None = None
    is_visible: bool | None = None


class CategoryRead(ORMSchema):
    id: int
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    accent: str
    parent_id: int | None = None
    position: int
    is_visible: bool
    post_count: int = 0


class TagRead(ORMSchema):
    id: int
    name: str
    slug: str
    accent: str
    usage_count: int


class TagCreate(Schema):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    accent: str = "secondary"
    description: str | None = None


class SeriesRead(ORMSchema):
    id: int
    title: str
    slug: str
    summary: str | None = None
    cover_url: str | None = None
    is_complete: bool


# --------------------------------------------------------------------- blocks
#: Keys each block type needs. Validation is deliberately shallow — the block
#: payload is meant to stay open so new renderer options do not need a backend
#: release — but a missing essential key is caught here rather than in the UI.
REQUIRED_BLOCK_KEYS: dict[str, tuple[str, ...]] = {
    BlockType.RICH_TEXT: ("html",),
    BlockType.MARKDOWN: ("source",),
    BlockType.HEADING: ("text",),
    BlockType.CODE: ("source",),
    BlockType.QUOTE: ("text",),
    BlockType.CALLOUT: ("html",),
    BlockType.LIST: ("items",),
    BlockType.TABLE: ("rows",),
    BlockType.IMAGE: ("url",),
    BlockType.GALLERY: ("items",),
    BlockType.VIDEO: ("url",),
    BlockType.AUDIO: ("url",),
    BlockType.FILE: ("url",),
    BlockType.EMBED: ("embed_url",),
    BlockType.POLL: (),
    BlockType.QUIZ: ("questions",),
    BlockType.DIVIDER: (),
    BlockType.BUTTON: ("label", "url"),
    BlockType.AD_SLOT: ("slot_key",),
    BlockType.HTML: ("html",),
    BlockType.MATH: ("latex",),
}


class ContentBlockIn(Schema):
    type: BlockType = BlockType.RICH_TEXT
    position: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    anchor: str | None = None
    is_hidden: bool = False
    #: Present when updating an existing block; absent means "create".
    id: int | None = None
    #: For POLL blocks the poll can be created inline with the post.
    poll: "PollIn | None" = None

    @model_validator(mode="after")
    def _check_payload(self) -> "ContentBlockIn":
        required = REQUIRED_BLOCK_KEYS.get(self.type, ())
        missing = [key for key in required if key not in self.data]
        if missing:
            raise ValueError(
                f"A {self.type} block needs: {', '.join(missing)}."
            )
        if self.type == BlockType.CODE:
            self.data.setdefault("language", "text")
            self.data.setdefault("show_line_numbers", True)
        if self.type == BlockType.IMAGE and not self.data.get("alt"):
            # Not fatal, but recorded so the editor can nudge the author.
            self.data.setdefault("alt", "")
        return self


class ContentBlockRead(ORMSchema):
    id: int
    type: str
    position: int
    data: dict[str, Any]
    settings: dict[str, Any]
    anchor: str | None = None
    is_hidden: bool


# ---------------------------------------------------------------------- polls
class PollOptionIn(Schema):
    id: int | None = None
    label: Annotated[str, Field(min_length=1, max_length=300)]
    description: str | None = None
    image_url: str | None = None
    icon: str | None = None
    accent: str | None = None
    position: int = 0


class PollIn(Schema):
    question: Annotated[str, Field(min_length=3, max_length=300)]
    description: str | None = None
    type: str = "single"
    options: Annotated[list[PollOptionIn], Field(min_length=2, max_length=20)]
    allow_multiple: bool = False
    max_selections: int = 1
    allow_anonymous: bool = True
    allow_vote_change: bool = True
    allow_write_in: bool = False
    hide_results_until_voted: bool = True
    hide_results_until_closed: bool = False
    opens_at: datetime | None = None
    closes_at: datetime | None = None


class PollOptionRead(ORMSchema):
    id: int
    label: str
    description: str | None = None
    image_url: str | None = None
    icon: str | None = None
    accent: str | None = None
    position: int
    is_write_in: bool
    vote_count: int
    #: Share of the total, 0–100. Filled in by the service layer.
    percentage: float = 0.0


class PollVoterRead(Schema):
    """One vote, for the poll owner/moderator — not shown to ordinary readers."""

    option_id: int
    option_label: str
    voter_name: str
    is_registered: bool
    voted_at: datetime


class PollRead(ORMSchema):
    id: int
    post_id: int | None = None
    question: str
    description: str | None = None
    type: str
    allow_multiple: bool
    max_selections: int
    allow_write_in: bool
    allow_vote_change: bool
    hide_results_until_voted: bool
    is_open: bool
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    total_votes: int
    total_voters: int
    options: list[PollOptionRead] = Field(default_factory=list)
    #: Option ids the caller already chose, empty when they have not voted.
    my_votes: list[int] = Field(default_factory=list)
    #: False when results are withheld until the reader votes or the poll closes.
    results_visible: bool = True


class PollVoteIn(Schema):
    option_ids: Annotated[list[int], Field(min_length=1, max_length=20)]
    #: Only used by ranked polls: option id → 1-based rank.
    ranks: dict[int, int] | None = None
    write_in: Annotated[str | None, Field(max_length=200)] = None


# ---------------------------------------------------------------------- posts
class PostBase(Schema):
    title: Annotated[str, Field(min_length=3, max_length=220)]
    subtitle: Annotated[str | None, Field(max_length=300)] = None
    excerpt: Annotated[str | None, Field(max_length=1000)] = None
    cover_url: str | None = None
    cover_caption: str | None = None
    category_id: int | None = None
    series_id: int | None = None
    series_position: int | None = None
    tags: Annotated[list[str], Field(max_length=15)] = Field(default_factory=list)
    visibility: PostVisibility = PostVisibility.PUBLIC
    allow_comments: bool = True
    allow_reactions: bool = True
    show_ads: bool = True
    layout_options: dict[str, Any] = Field(default_factory=dict)
    meta_title: Annotated[str | None, Field(max_length=200)] = None
    meta_description: Annotated[str | None, Field(max_length=320)] = None
    canonical_url: str | None = None
    og_image_url: str | None = None
    language: str = "en"


class PostCreate(PostBase):
    slug: str | None = None
    blocks: list[ContentBlockIn] = Field(default_factory=list)
    #: ``draft`` saves privately; ``submitted`` enters review; ``published``
    #: goes live and is only honoured for accounts with ``post:publish``.
    status: PostStatus = PostStatus.DRAFT
    scheduled_for: datetime | None = None


class PostGuestCreate(PostBase):
    """A submission from a visitor who is not signed in."""

    blocks: list[ContentBlockIn] = Field(default_factory=list)
    guest_name: Annotated[str, Field(min_length=2, max_length=120)]
    guest_email: EmailStr
    byline_override: Annotated[str | None, Field(max_length=160)] = None
    accept_terms: bool = True

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Accept the contributor terms to submit a post.")
        return value


class PostUpdate(Schema):
    title: Annotated[str | None, Field(min_length=3, max_length=220)] = None
    slug: str | None = None
    subtitle: str | None = None
    excerpt: str | None = None
    cover_url: str | None = None
    cover_caption: str | None = None
    category_id: int | None = None
    series_id: int | None = None
    series_position: int | None = None
    tags: list[str] | None = None
    visibility: PostVisibility | None = None
    allow_comments: bool | None = None
    allow_reactions: bool | None = None
    show_ads: bool | None = None
    layout_options: dict[str, Any] | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    og_image_url: str | None = None
    blocks: list[ContentBlockIn] | None = None
    change_note: Annotated[str | None, Field(max_length=300)] = None


class PostStatusChange(Schema):
    status: PostStatus
    scheduled_for: datetime | None = None
    reason: Annotated[str | None, Field(max_length=500)] = None


class PostSummary(ORMSchema):
    """List-view shape — no blocks, so feeds stay cheap."""

    id: int
    title: str
    slug: str
    subtitle: str | None = None
    excerpt: str | None = None
    cover_url: str | None = None
    status: str
    visibility: str
    published_at: datetime | None = None
    created_at: datetime
    is_featured: bool
    is_pinned: bool
    reading_minutes: int
    view_count: int
    reaction_count: int
    comment_count: int
    byline: str
    author: UserPublic | None = None
    category: CategoryRead | None = None
    tags: list[TagRead] = Field(default_factory=list)


class PostDetail(PostSummary):
    blocks: list[ContentBlockRead] = Field(default_factory=list)
    polls: list[PollRead] = Field(default_factory=list)
    series: SeriesRead | None = None
    series_position: int | None = None
    allow_comments: bool
    allow_reactions: bool
    show_ads: bool
    layout_options: dict[str, Any] = Field(default_factory=dict)
    meta_title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    og_image_url: str | None = None
    word_count: int
    share_count: int
    #: Reaction the caller already left, if any.
    my_reaction: str | None = None
    is_bookmarked: bool = False
    #: Permissions the caller holds over this specific post.
    can_edit: bool = False
    can_delete: bool = False
    can_moderate: bool = False


class PostReactionIn(Schema):
    type: ReactionType = ReactionType.LIKE


class ReactionSummary(Schema):
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    my_reaction: str | None = None


class PostViewIn(Schema):
    referrer: Annotated[str | None, Field(max_length=500)] = None
    seconds_on_page: int = 0
    scroll_depth: Annotated[int, Field(ge=0, le=100)] = 0


class PostModerationDecision(Schema):
    approve: bool
    #: Publish immediately on approval instead of returning to draft.
    publish: bool = True
    reason: Annotated[str | None, Field(max_length=500)] = None
    notify_author: bool = True


ContentBlockIn.model_rebuild()
