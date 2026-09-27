"""Categories, tags and series used to organise the blog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.post import Post


post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base, PKMixin, TimestampMixin):
    """A single-parent tree. A post belongs to at most one category."""

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(80), index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    #: Bootstrap Icons class, e.g. ``bi-cpu``.
    icon: Mapped[str | None] = mapped_column(String(60))
    #: Webpixels colour token, e.g. ``primary`` or ``warning``.
    accent: Mapped[str] = mapped_column(String(24), default="primary")
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)

    parent: Mapped["Category | None"] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    posts: Mapped[list["Post"]] = relationship(back_populates="category")


class Tag(Base, PKMixin, TimestampMixin):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(60), index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    accent: Mapped[str] = mapped_column(String(24), default="secondary")
    #: Denormalised counter kept in step by the post service.
    usage_count: Mapped[int] = mapped_column(Integer, default=0, index=True)

    posts: Mapped[list["Post"]] = relationship(
        secondary=post_tags, back_populates="tags"
    )


class Series(Base, PKMixin, TimestampMixin):
    """An ordered run of posts, e.g. a multi-part write-up."""

    __tablename__ = "series"

    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(String(500))
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    posts: Mapped[list["Post"]] = relationship(
        back_populates="series", order_by="Post.series_position"
    )
