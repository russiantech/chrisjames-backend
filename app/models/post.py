"""The blog post and everything hanging off it.

A post is a shell of metadata plus an ordered list of :class:`ContentBlock`
rows. Each block carries a ``type`` and a JSON ``data`` payload, which is what
makes the editor open-ended: text, markdown, code, images, galleries, video,
audio, embeds, polls, tables and advert slots are all just block types, and a
new format needs a renderer on the client but no database migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.enums import BlockType, PostStatus, PostVisibility, ReactionType
from app.models.taxonomy import post_tags

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.media import MediaAsset
    from app.models.poll import Poll
    from app.models.taxonomy import Category, Series, Tag
    from app.models.user import User


class Post(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_post_feed", "status", "visibility", "published_at"),
        Index("ix_post_author_status", "author_id", "status"),
    )

    # identity ----------------------------------------------------------
    title: Mapped[str] = mapped_column(String(220), index=True)
    slug: Mapped[str] = mapped_column(String(250), unique=True, index=True)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    excerpt: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(String(500))
    cover_caption: Mapped[str | None] = mapped_column(String(300))

    # lifecycle ---------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(20), default=PostStatus.DRAFT, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default=PostVisibility.PUBLIC, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # authorship --------------------------------------------------------
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    #: Set when an anonymous visitor submits a post without registering.
    guest_name: Mapped[str | None] = mapped_column(String(120))
    guest_email: Mapped[str | None] = mapped_column(String(255))
    #: Free-text credit shown instead of the account name, if provided.
    byline_override: Mapped[str | None] = mapped_column(String(160))

    # organisation ------------------------------------------------------
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL")
    )
    series_position: Mapped[int | None] = mapped_column(Integer)

    # presentation ------------------------------------------------------
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_reactions: Mapped[bool] = mapped_column(Boolean, default=True)
    show_ads: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Per-post layout knobs, e.g. ``{"toc": true, "width": "narrow"}``.
    layout_options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # seo ---------------------------------------------------------------
    meta_title: Mapped[str | None] = mapped_column(String(200))
    meta_description: Mapped[str | None] = mapped_column(String(320))
    canonical_url: Mapped[str | None] = mapped_column(String(500))
    og_image_url: Mapped[str | None] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(12), default="en")

    # metrics -----------------------------------------------------------
    view_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    unique_view_count: Mapped[int] = mapped_column(Integer, default=0)
    reaction_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=1)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    #: Rolling popularity score used to order the "trending" rail.
    trending_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)

    # relationships -----------------------------------------------------
    author: Mapped["User | None"] = relationship(
        back_populates="posts", foreign_keys=[author_id], lazy="joined"
    )
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])
    category: Mapped["Category | None"] = relationship(
        back_populates="posts", lazy="joined"
    )
    series: Mapped["Series | None"] = relationship(back_populates="posts")
    tags: Mapped[list["Tag"]] = relationship(
        secondary=post_tags, back_populates="posts", lazy="selectin"
    )
    blocks: Mapped[list["ContentBlock"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="ContentBlock.position",
        lazy="selectin",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    polls: Mapped[list["Poll"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    revisions: Mapped[list["PostRevision"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostRevision.created_at.desc()",
    )
    reactions: Mapped[list["PostReaction"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["MediaAsset"]] = relationship(back_populates="post")

    @property
    def is_live(self) -> bool:
        return self.status == PostStatus.PUBLISHED and self.deleted_at is None

    @property
    def byline(self) -> str:
        if self.byline_override:
            return self.byline_override
        if self.author is not None:
            return self.author.display_name
        return self.guest_name or "Guest contributor"


class ContentBlock(Base, PKMixin, TimestampMixin):
    """One ordered chunk of a post body."""

    __tablename__ = "content_blocks"
    __table_args__ = (Index("ix_block_post_position", "post_id", "position"),)

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30), default=BlockType.RICH_TEXT)
    position: Mapped[int] = mapped_column(Integer, default=0)

    #: Shape depends on ``type``. Examples:
    #:   rich_text  {"html": "<p>…</p>"}
    #:   markdown   {"source": "# hi"}
    #:   code       {"language": "python", "source": "...", "filename": "app.py",
    #:               "highlight_lines": [3, 4], "show_line_numbers": true}
    #:   image      {"media_id": 12, "url": "...", "alt": "...", "caption": "...",
    #:               "width": 1600, "height": 900, "lightbox": true}
    #:   gallery    {"items": [{"media_id": 1, "caption": "..."}], "layout": "masonry"}
    #:   video      {"media_id": 4, "url": "...", "poster_url": "...",
    #:               "provider": "upload|youtube|vimeo", "captions_url": "..."}
    #:   audio      {"media_id": 7, "url": "...", "transcript": "...", "waveform": []}
    #:   embed      {"provider": "youtube", "embed_url": "...", "aspect": "16x9"}
    #:   poll       {"poll_id": 3}
    #:   table      {"columns": [...], "rows": [[...]], "striped": true}
    #:   callout    {"tone": "info", "icon": "bi-lightbulb", "html": "..."}
    #:   ad_slot    {"slot_key": "in_article_1"}
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    #: Optional per-block presentation, e.g. ``{"align": "wide", "theme": "dark"}``.
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Anchor used for deep links and the table of contents.
    anchor: Mapped[str | None] = mapped_column(String(120))
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    post: Mapped[Post] = relationship(back_populates="blocks")


class PostRevision(Base, PKMixin, TimestampMixin):
    """Immutable snapshot of a post, written on every meaningful save."""

    __tablename__ = "post_revisions"

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    editor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(220))
    #: Full serialised body at this point in time.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    change_note: Mapped[str | None] = mapped_column(String(300))

    post: Mapped[Post] = relationship(back_populates="revisions")


class PostReaction(Base, PKMixin, TimestampMixin):
    __tablename__ = "post_reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_reaction_user"),
        UniqueConstraint("post_id", "anon_key", name="uq_post_reaction_anon"),
    )

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    #: Hashed IP + user-agent, so signed-out readers can react exactly once.
    anon_key: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(20), default=ReactionType.LIKE)

    post: Mapped[Post] = relationship(back_populates="reactions")


class Bookmark(Base, PKMixin, TimestampMixin):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_bookmark"),)

    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    note: Mapped[str | None] = mapped_column(String(300))


class PostView(Base, PKMixin, TimestampMixin):
    """One row per read, aggregated nightly into the counters on ``Post``."""

    __tablename__ = "post_views"
    __table_args__ = (Index("ix_view_post_day", "post_id", "created_at"),)

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    anon_key: Mapped[str | None] = mapped_column(String(64), index=True)
    referrer: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(2))
    device: Mapped[str | None] = mapped_column(String(20))
    seconds_on_page: Mapped[int] = mapped_column(Integer, default=0)
    scroll_depth: Mapped[int] = mapped_column(Integer, default=0)
