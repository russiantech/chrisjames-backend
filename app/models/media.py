"""Uploaded files: images, video, audio, documents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.enums import MediaKind

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class MediaAsset(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "media_assets"

    # storage -----------------------------------------------------------
    #: Path relative to ``MEDIA_ROOT`` (local) or the object key (S3/R2).
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    url: Mapped[str] = mapped_column(String(700))
    #: Derived renditions, e.g. ``{"thumb": "...", "medium": "...", "webp": "..."}``.
    variants: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)

    # description -------------------------------------------------------
    original_filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=MediaKind.OTHER, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)

    # media specifics ---------------------------------------------------
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    #: Dominant colour, used as an image placeholder before load.
    placeholder_color: Mapped[str | None] = mapped_column(String(9))
    blurhash: Mapped[str | None] = mapped_column(String(64))

    # editorial ---------------------------------------------------------
    alt_text: Mapped[str | None] = mapped_column(String(400))
    caption: Mapped[str | None] = mapped_column(Text)
    credit: Mapped[str | None] = mapped_column(String(200))
    #: Free-form labels for the media library filter.
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    transcript: Mapped[str | None] = mapped_column(Text)
    #: Extra data from the pipeline, e.g. EXIF or ffprobe output.
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # ownership ---------------------------------------------------------
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Bumped whenever a block references the asset, so orphans are findable.
    reference_count: Mapped[int] = mapped_column(Integer, default=0)

    owner: Mapped["User | None"] = relationship(back_populates="media")
    post: Mapped["Post | None"] = relationship(back_populates="attachments")

    @staticmethod
    def kind_for(content_type: str) -> str:
        if content_type.startswith("image/"):
            return MediaKind.IMAGE
        if content_type.startswith("video/"):
            return MediaKind.VIDEO
        if content_type.startswith("audio/"):
            return MediaKind.AUDIO
        if content_type in {"application/zip", "application/x-tar", "application/gzip"}:
            return MediaKind.ARCHIVE
        if content_type.startswith("text/") or content_type in {
            "application/pdf",
            "application/msword",
        }:
            return MediaKind.DOCUMENT
        return MediaKind.OTHER
