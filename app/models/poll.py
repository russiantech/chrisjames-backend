"""Polls embedded in posts: single choice, multiple choice, ranked and rating."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

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

from app.db.base_class import Base, PKMixin, TimestampMixin
from app.models.enums import PollType

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Poll(Base, PKMixin, TimestampMixin):
    __tablename__ = "polls"

    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(20), default=PollType.SINGLE)

    # rules -------------------------------------------------------------
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=False)
    max_selections: Mapped[int] = mapped_column(Integer, default=1)
    allow_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_vote_change: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_write_in: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Withhold the tally until the reader has voted.
    hide_results_until_voted: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Withhold the tally until the poll closes.
    hide_results_until_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    # lifecycle ---------------------------------------------------------
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    total_votes: Mapped[int] = mapped_column(Integer, default=0)
    total_voters: Mapped[int] = mapped_column(Integer, default=0)

    post: Mapped["Post | None"] = relationship(back_populates="polls")
    options: Mapped[list["PollOption"]] = relationship(
        back_populates="poll",
        cascade="all, delete-orphan",
        order_by="PollOption.position",
        lazy="selectin",
    )
    votes: Mapped[list["PollVote"]] = relationship(
        back_populates="poll", cascade="all, delete-orphan"
    )

    @property
    def accepting_votes(self) -> bool:
        now = datetime.now(tz=(self.closes_at.tzinfo if self.closes_at else None))
        if not self.is_open:
            return False
        if self.opens_at and self.opens_at > now:
            return False
        if self.closes_at and self.closes_at <= now:
            return False
        return True


class PollOption(Base, PKMixin, TimestampMixin):
    __tablename__ = "poll_options"

    poll_id: Mapped[int] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    #: Options can carry an image, so a poll can be visual.
    image_url: Mapped[str | None] = mapped_column(String(500))
    icon: Mapped[str | None] = mapped_column(String(60))
    accent: Mapped[str | None] = mapped_column(String(24))
    position: Mapped[int] = mapped_column(Integer, default=0)
    #: True for options typed in by readers when ``allow_write_in`` is on.
    is_write_in: Mapped[bool] = mapped_column(Boolean, default=False)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)

    poll: Mapped[Poll] = relationship(back_populates="options")
    votes: Mapped[list["PollVote"]] = relationship(
        back_populates="option", cascade="all, delete-orphan"
    )


class PollVote(Base, PKMixin, TimestampMixin):
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("option_id", "user_id", name="uq_poll_vote_user_option"),
        UniqueConstraint("option_id", "anon_key", name="uq_poll_vote_anon_option"),
        Index("ix_poll_vote_lookup", "poll_id", "user_id", "anon_key"),
    )

    poll_id: Mapped[int] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"), index=True
    )
    option_id: Mapped[int] = mapped_column(
        ForeignKey("poll_options.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    anon_key: Mapped[str | None] = mapped_column(String(64), index=True)
    #: 1-based position for ranked polls; the score for rating polls.
    rank: Mapped[int | None] = mapped_column(Integer)
    #: Anything extra the vote carries, e.g. ``{"comment": "..."}``.
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    poll: Mapped[Poll] = relationship(back_populates="votes")
    option: Mapped[PollOption] = relationship(back_populates="votes")
    user: Mapped["User | None"] = relationship()
