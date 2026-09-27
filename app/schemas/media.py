# # app/schemas/media.py
# """Media library schemas."""

# from __future__ import annotations

# from datetime import datetime
# from typing import Annotated, Any

# from pydantic import Field

# from app.schemas.common import ORMSchema, Schema
# from app.schemas.user import UserPublic


# class MediaRead(ORMSchema):
#     id: int
#     url: str
#     storage_key: str
#     original_filename: str
#     content_type: str
#     kind: str
#     size_bytes: int
#     width: int | None = None
#     height: int | None = None
#     duration_seconds: float | None = None
#     placeholder_color: str | None = None
#     variants: dict[str, str] = Field(default_factory=dict)
#     alt_text: str | None = None
#     caption: str | None = None
#     credit: str | None = None
#     labels: list[str] = Field(default_factory=list)
#     transcript: str | None = None
#     is_public: bool
#     reference_count: int
#     created_at: datetime
#     owner: UserPublic | None = None


# class MediaUpdate(Schema):
#     alt_text: Annotated[str | None, Field(max_length=400)] = None
#     caption: str | None = None
#     credit: Annotated[str | None, Field(max_length=200)] = None
#     labels: list[str] | None = None
#     transcript: str | None = None
#     is_public: bool | None = None


# class MediaUploadResult(Schema):
#     asset: MediaRead
#     #: True when an identical file was already in the library.
#     deduplicated: bool = False


# class SignedUploadRequest(Schema):
#     """Ask for a direct-to-storage URL, used for large video and audio."""

#     filename: Annotated[str, Field(max_length=300)]
#     content_type: Annotated[str, Field(max_length=120)]
#     size_bytes: Annotated[int, Field(gt=0)]


# class SignedUploadResponse(Schema):
#     upload_url: str
#     method: str = "PUT"
#     headers: dict[str, str] = Field(default_factory=dict)
#     storage_key: str
#     #: Call this once the upload finishes so the asset row is created.
#     complete_url: str
#     expires_in: int = 900


# class MediaProbe(Schema):
#     """Technical metadata extracted after upload."""

#     width: int | None = None
#     height: int | None = None
#     duration_seconds: float | None = None
#     meta: dict[str, Any] = Field(default_factory=dict)




# # ======================= v2 ======= MEDIA UPLOAD / ATTACH-BY-LINK SCHEMAS =======================
# """Schemas for the /media endpoints (direct upload + attach-by-link)."""

# # from __future__ import annotations // Already imported at the top

# from typing import Literal

# from pydantic import BaseModel, ConfigDict, HttpUrl

# MediaKind = Literal["image", "video", "audio", "document", "other"]


# class MediaOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: int
#     url: str
#     kind: MediaKind
#     filename: str | None = None
#     content_type: str | None = None
#     size_bytes: int | None = None


# class MediaLinkIn(BaseModel):
#     """Attach an external file by URL instead of uploading it."""

#     url: HttpUrl





# v2
"""Media library schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field

from app.schemas.common import ORMSchema, Schema
from app.schemas.user import UserPublic


class MediaRead(ORMSchema):
    id: int
    url: str
    storage_key: str
    original_filename: str
    content_type: str
    kind: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    placeholder_color: str | None = None
    variants: dict[str, str] = Field(default_factory=dict)
    alt_text: str | None = None
    caption: str | None = None
    credit: str | None = None
    labels: list[str] = Field(default_factory=list)
    transcript: str | None = None
    is_public: bool
    reference_count: int
    created_at: datetime
    owner: UserPublic | None = None


class MediaUpdate(Schema):
    alt_text: Annotated[str | None, Field(max_length=400)] = None
    caption: str | None = None
    credit: Annotated[str | None, Field(max_length=200)] = None
    labels: list[str] | None = None
    transcript: str | None = None
    is_public: bool | None = None


class MediaUploadResult(Schema):
    asset: MediaRead
    #: True when an identical file was already in the library.
    deduplicated: bool = False


class SignedUploadRequest(Schema):
    """Ask for a direct-to-storage URL, used for large video and audio."""

    filename: Annotated[str, Field(max_length=300)]
    content_type: Annotated[str, Field(max_length=120)]
    size_bytes: Annotated[int, Field(gt=0)]


class SignedUploadResponse(Schema):
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)
    storage_key: str
    #: Call this once the upload finishes so the asset row is created.
    complete_url: str
    expires_in: int = 900


class MediaProbe(Schema):
    """Technical metadata extracted after upload."""

    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

