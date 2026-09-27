"""Threaded comments, replies, reactions and reports."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

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

from app.db.base_class import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.enums import ModerationState, ReactionType

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Comment(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    """A comment or a reply.

    Threading uses ``parent_id`` for the direct parent plus a materialised
    ``path`` (``"12.48.103"``) so a whole subtree can be fetched and ordered in
    one query without recursion.
    """

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comment_post_thread", "post_id", "path"),
        Index("ix_comment_moderation", "moderation_state", "created_at"),
    )

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(500), default="", index=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)

    # author ------------------------------------------------------------
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    guest_name: Mapped[str | None] = mapped_column(String(120))
    guest_email: Mapped[str | None] = mapped_column(String(255))
    guest_website: Mapped[str | None] = mapped_column(String(255))

    # body --------------------------------------------------------------
    #: Raw markdown as typed, including fenced code blocks.
    body: Mapped[str] = mapped_column(Text)
    #: Sanitised HTML rendered from ``body`` at write time.
    body_html: Mapped[str] = mapped_column(Text, default="")
    #: Usernames extracted from ``@mentions``, used to fan out notifications.
    mentions: Mapped[list[str]] = mapped_column(JSON, default=list)

    # moderation --------------------------------------------------------
    moderation_state: Mapped[str] = mapped_column(
        String(20), default=ModerationState.APPROVED, index=True
    )
    moderated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_note: Mapped[str | None] = mapped_column(String(300))
    spam_score: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)

    # presentation ------------------------------------------------------
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Set when the site owner replies, so the UI can badge it.
    is_author_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    reaction_count: Mapped[int] = mapped_column(Integer, default=0)

    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    # relationships -----------------------------------------------------
    post: Mapped["Post"] = relationship(back_populates="comments")
    author: Mapped["User | None"] = relationship(
        back_populates="comments", foreign_keys=[author_id], lazy="joined"
    )
    parent: Mapped["Comment | None"] = relationship(
        remote_side="Comment.id", back_populates="replies"
    )
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["CommentReaction"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan"
    )

    @property
    def is_visible(self) -> bool:
        return (
            self.moderation_state == ModerationState.APPROVED
            and self.deleted_at is None
        )

    @property
    def display_name(self) -> str:
        if self.author is not None:
            return self.author.display_name
        return self.guest_name or "Anonymous"

    def build_path(self) -> str:
        if self.parent is None:
            return str(self.id)
        return f"{self.parent.path}.{self.id}"


class CommentReaction(Base, PKMixin, TimestampMixin):
    __tablename__ = "comment_reactions"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_reaction_user"),
        UniqueConstraint("comment_id", "anon_key", name="uq_comment_reaction_anon"),
    )

    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    anon_key: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(20), default=ReactionType.LIKE)

    comment: Mapped[Comment] = relationship(back_populates="reactions")


class CommentReport(Base, PKMixin, TimestampMixin):
    """A reader flagging a comment. Enough reports auto-hide it for review."""

    __tablename__ = "comment_reports"

    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    reporter_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
