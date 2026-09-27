# """Media library: upload, browse, annotate, delete."""

# from __future__ import annotations

# from pathlib import Path
# from typing import Annotated

# from fastapi import APIRouter, File, Form, Query, UploadFile, status
# from sqlalchemy import func, or_, select

# from app.api.deps import CurrentUser, DbSession, Pagination, require
# from app.core.exceptions import NotFound, PermissionDenied
# from app.core.permissions import Perm
# from app.models.media import MediaAsset
# from app.models.user import User
# from app.schemas.common import Message, Page
# from app.schemas.media import (
#     MediaRead,
#     MediaUpdate,
#     MediaUploadResult,
#     SignedUploadRequest,
#     SignedUploadResponse,
# )
# from app.services.storage import build_key, get_storage, probe_image, validate_upload

# router = APIRouter(prefix="/media", tags=["media"])


# @router.post("", response_model=MediaUploadResult, status_code=status.HTTP_201_CREATED)
# async def upload(
#     db: DbSession,
#     user: Annotated[User, require(Perm.MEDIA_UPLOAD)],
#     file: Annotated[UploadFile, File(description="The file to store")],
#     alt_text: Annotated[str | None, Form()] = None,
#     caption: Annotated[str | None, Form()] = None,
#     labels: Annotated[str | None, Form(description="Comma separated")] = None,
#     post_id: Annotated[int | None, Form()] = None,
# ) -> MediaUploadResult:
#     """Store one file and return the asset row the editor references."""
#     raw = await file.read()
#     content_type = validate_upload(
#         file.filename or "upload", file.content_type or "", len(raw)
#     )

#     import hashlib
#     import io

#     checksum = hashlib.sha256(raw).hexdigest()
#     duplicate = await db.scalar(
#         select(MediaAsset).where(
#             MediaAsset.checksum == checksum,
#             MediaAsset.owner_id == user.id,
#             MediaAsset.deleted_at.is_(None),
#         )
#     )
#     if duplicate is not None:
#         return MediaUploadResult(asset=MediaRead.model_validate(duplicate), deduplicated=True)

#     storage = get_storage()
#     key = build_key(file.filename or "upload")
#     stored = storage.save(io.BytesIO(raw), key, content_type)

#     asset = MediaAsset(
#         storage_key=stored.storage_key,
#         storage_backend=getattr(storage, "name", "local"),
#         url=stored.url,
#         original_filename=file.filename or "upload",
#         content_type=content_type,
#         kind=MediaAsset.kind_for(content_type),
#         size_bytes=stored.size_bytes,
#         checksum=stored.checksum,
#         alt_text=alt_text,
#         caption=caption,
#         labels=[l.strip() for l in (labels or "").split(",") if l.strip()],
#         owner_id=user.id,
#         post_id=post_id,
#     )

#     if asset.kind == "image":
#         from app.core.config import settings

#         for key_name, value in probe_image(Path(settings.MEDIA_ROOT) / stored.storage_key).items():
#             setattr(asset, key_name, value)

#     db.add(asset)
#     await db.commit()
#     await db.refresh(asset, ["owner"])
#     return MediaUploadResult(asset=MediaRead.model_validate(asset))


# @router.post("/signed-upload", response_model=SignedUploadResponse)
# async def signed_upload(
#     payload: SignedUploadRequest,
#     _: Annotated[User, require(Perm.MEDIA_UPLOAD)],
# ) -> SignedUploadResponse:
#     """Direct-to-storage upload for large video and audio.

#     The local backend has no presign step, so this returns the normal upload
#     route; switching to S3 or R2 makes it a real signed URL with no client
#     change.
#     """
#     from app.core.config import settings

#     validate_upload(payload.filename, payload.content_type, payload.size_bytes)
#     key = build_key(payload.filename)
#     storage = get_storage()
#     try:
#         signed = storage.presign_put(key, payload.content_type)
#         return SignedUploadResponse(
#             upload_url=signed["url"],
#             headers=signed.get("headers", {}),
#             storage_key=key,
#             complete_url=f"{settings.API_V1_PREFIX}/media/complete",
#         )
#     except NotImplementedError:
#         return SignedUploadResponse(
#             upload_url=f"{settings.API_V1_PREFIX}/media",
#             method="POST",
#             storage_key=key,
#             complete_url=f"{settings.API_V1_PREFIX}/media",
#         )


# @router.get("", response_model=Page[MediaRead])
# async def list_media(
#     db: DbSession,
#     page: Pagination,
#     user: Annotated[User, require(Perm.MEDIA_UPLOAD)],
#     kind: str | None = None,
#     q: Annotated[str | None, Query(max_length=120)] = None,
#     mine: bool = False,
# ) -> Page[MediaRead]:
#     stmt = select(MediaAsset).where(MediaAsset.deleted_at.is_(None))
#     if mine or not user.has_permission(Perm.MEDIA_DELETE_ANY):
#         stmt = stmt.where(MediaAsset.owner_id == user.id)
#     if kind:
#         stmt = stmt.where(MediaAsset.kind == kind)
#     if q:
#         like = f"%{q}%"
#         stmt = stmt.where(
#             or_(
#                 MediaAsset.original_filename.ilike(like),
#                 MediaAsset.alt_text.ilike(like),
#                 MediaAsset.caption.ilike(like),
#             )
#         )

#     total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
#     rows = (
#         await db.scalars(
#             stmt.order_by(MediaAsset.created_at.desc())
#             .offset(page.offset)
#             .limit(page.limit)
#         )
#     ).all()
#     return Page.build(
#         [MediaRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
#     )


# @router.patch("/{asset_id}", response_model=MediaRead)
# async def update_media(
#     asset_id: int, payload: MediaUpdate, db: DbSession, user: CurrentUser
# ) -> MediaRead:
#     asset = await db.get(MediaAsset, asset_id)
#     if asset is None or asset.deleted_at is not None:
#         raise NotFound("No file with that id.")
#     if asset.owner_id != user.id and not user.has_permission(Perm.MEDIA_DELETE_ANY):
#         raise PermissionDenied("You can only edit your own uploads.")

#     for field, value in payload.model_dump(exclude_unset=True).items():
#         setattr(asset, field, value)
#     await db.commit()
#     return MediaRead.model_validate(asset)


# @router.delete("/{asset_id}", response_model=Message)
# async def delete_media(asset_id: int, db: DbSession, user: CurrentUser) -> Message:
#     asset = await db.get(MediaAsset, asset_id)
#     if asset is None or asset.deleted_at is not None:
#         raise NotFound("No file with that id.")

#     owns = asset.owner_id == user.id
#     if not (owns and user.has_permission(Perm.MEDIA_DELETE_OWN)) and not user.has_permission(
#         Perm.MEDIA_DELETE_ANY
#     ):
#         raise PermissionDenied("You can only delete your own uploads.")

#     if asset.reference_count > 0:
#         # Keep the bytes; a post still points at them.
#         asset.soft_delete()
#         await db.commit()
#         return Message(
#             detail=f"Hidden from the library. {asset.reference_count} post(s) still use it.",
#             code="soft_deleted",
#         )

#     get_storage().delete(asset.storage_key)
#     await db.delete(asset)
#     await db.commit()
#     return Message(detail="File deleted.")


# v2
# """Media library: upload, browse, annotate, delete."""

# from __future__ import annotations

# import hashlib
# import io
# from pathlib import Path
# from typing import Annotated

# from fastapi import APIRouter, File, Form, Query, UploadFile, status
# from sqlalchemy import func, or_, select

# from app.api.deps import CurrentUser, DbSession, Pagination, require
# from app.core.exceptions import NotFound, PermissionDenied
# from app.core.permissions import Perm
# from app.models.media import MediaAsset
# from app.models.user import User
# from app.schemas.common import Message, Page
# from app.schemas.media import (
#     MediaRead,
#     MediaUpdate,
#     MediaUploadResult,
#     SignedUploadRequest,
#     SignedUploadResponse,
# )
# from app.services.storage import build_key, get_storage, probe_image, validate_upload

# router = APIRouter(prefix="/media", tags=["media"])


# @router.post("", response_model=MediaUploadResult, status_code=status.HTTP_201_CREATED)
# async def upload(
#     db: DbSession,
#     user: Annotated[User, require(Perm.MEDIA_UPLOAD)],
#     file: Annotated[UploadFile, File(description="The file to store")],
#     alt_text: Annotated[str | None, Form()] = None,
#     caption: Annotated[str | None, Form()] = None,
#     labels: Annotated[str | None, Form(description="Comma separated")] = None,
#     post_id: Annotated[int | None, Form()] = None,
# ) -> MediaUploadResult:
#     """Store one file and return the asset row the editor references."""
#     raw = await file.read()
#     content_type = validate_upload(
#         file.filename or "upload", file.content_type or "", len(raw)
#     )

#     checksum = hashlib.sha256(raw).hexdigest()
#     duplicate = await db.scalar(
#         select(MediaAsset).where(
#             MediaAsset.checksum == checksum,
#             MediaAsset.owner_id == user.id,
#             MediaAsset.deleted_at.is_(None),
#         )
#     )
#     if duplicate is not None:
#         return MediaUploadResult(asset=MediaRead.model_validate(duplicate), deduplicated=True)

#     storage = get_storage()
#     key = build_key(file.filename or "upload")
#     stored = storage.save(io.BytesIO(raw), key, content_type)

#     asset = MediaAsset(
#         storage_key=stored.storage_key,
#         storage_backend=getattr(storage, "name", "local"),
#         url=stored.url,
#         original_filename=file.filename or "upload",
#         content_type=content_type,
#         kind=MediaAsset.kind_for(content_type),
#         size_bytes=stored.size_bytes,
#         checksum=stored.checksum,
#         alt_text=alt_text,
#         caption=caption,
#         labels=[l.strip() for l in (labels or "").split(",") if l.strip()],
#         owner_id=user.id,
#         post_id=post_id,
#     )

#     if asset.kind == "image":
#         from app.core.config import settings

#         for key_name, value in probe_image(Path(settings.MEDIA_ROOT) / stored.storage_key).items():
#             setattr(asset, key_name, value)

#     db.add(asset)
#     await db.commit()
#     await db.refresh(asset, ["owner"])
#     return MediaUploadResult(asset=MediaRead.model_validate(asset))


# @router.post("/signed-upload", response_model=SignedUploadResponse)
# async def signed_upload(
#     payload: SignedUploadRequest,
#     _: Annotated[User, require(Perm.MEDIA_UPLOAD)],
# ) -> SignedUploadResponse:
#     """Direct-to-storage upload for large video and audio.

#     The local backend has no presign step, so this returns the normal upload
#     route; switching to S3 or R2 makes it a real signed URL with no client
#     change.
#     """
#     from app.core.config import settings

#     validate_upload(payload.filename, payload.content_type, payload.size_bytes)
#     key = build_key(payload.filename)
#     storage = get_storage()
#     try:
#         signed = storage.presign_put(key, payload.content_type)
#         return SignedUploadResponse(
#             upload_url=signed["url"],
#             headers=signed.get("headers", {}),
#             storage_key=key,
#             complete_url=f"{settings.API_V1_PREFIX}/media/complete",
#         )
#     except NotImplementedError:
#         return SignedUploadResponse(
#             upload_url=f"{settings.API_V1_PREFIX}/media",
#             method="POST",
#             storage_key=key,
#             complete_url=f"{settings.API_V1_PREFIX}/media",
#         )


# @router.get("", response_model=Page[MediaRead])
# async def list_media(
#     db: DbSession,
#     page: Pagination,
#     user: Annotated[User, require(Perm.MEDIA_UPLOAD)],
#     kind: str | None = None,
#     q: Annotated[str | None, Query(max_length=120)] = None,
#     mine: bool = False,
# ) -> Page[MediaRead]:
#     stmt = select(MediaAsset).where(MediaAsset.deleted_at.is_(None))
#     if mine or not user.has_permission(Perm.MEDIA_DELETE_ANY):
#         stmt = stmt.where(MediaAsset.owner_id == user.id)
#     if kind:
#         stmt = stmt.where(MediaAsset.kind == kind)
#     if q:
#         like = f"%{q}%"
#         stmt = stmt.where(
#             or_(
#                 MediaAsset.original_filename.ilike(like),
#                 MediaAsset.alt_text.ilike(like),
#                 MediaAsset.caption.ilike(like),
#             )
#         )

#     total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
#     rows = (
#         await db.scalars(
#             stmt.order_by(MediaAsset.created_at.desc())
#             .offset(page.offset)
#             .limit(page.limit)
#         )
#     ).all()
#     return Page.build(
#         [MediaRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
#     )


# @router.patch("/{asset_id}", response_model=MediaRead)
# async def update_media(
#     asset_id: int, payload: MediaUpdate, db: DbSession, user: CurrentUser
# ) -> MediaRead:
#     asset = await db.get(MediaAsset, asset_id)
#     if asset is None or asset.deleted_at is not None:
#         raise NotFound("No file with that id.")
#     if asset.owner_id != user.id and not user.has_permission(Perm.MEDIA_DELETE_ANY):
#         raise PermissionDenied("You can only edit your own uploads.")

#     for field, value in payload.model_dump(exclude_unset=True).items():
#         setattr(asset, field, value)
#     await db.commit()
#     return MediaRead.model_validate(asset)


# @router.delete("/{asset_id}", response_model=Message)
# async def delete_media(asset_id: int, db: DbSession, user: CurrentUser) -> Message:
#     asset = await db.get(MediaAsset, asset_id)
#     if asset is None or asset.deleted_at is not None:
#         raise NotFound("No file with that id.")

#     owns = asset.owner_id == user.id
#     if not (owns and user.has_permission(Perm.MEDIA_DELETE_OWN)) and not user.has_permission(
#         Perm.MEDIA_DELETE_ANY
#     ):
#         raise PermissionDenied("You can only delete your own uploads.")

#     if asset.reference_count > 0:
#         # Keep the bytes; a post still points at them.
#         asset.soft_delete()
#         await db.commit()
#         return Message(
#             detail=f"Hidden from the library. {asset.reference_count} post(s) still use it.",
#             code="soft_deleted",
#         )

#     get_storage().delete(asset.storage_key)
#     await db.delete(asset)
#     await db.commit()
#     return Message(detail="File deleted.")




# v3
"""Media library: upload, browse, annotate, delete."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession, Pagination, require
from app.core.exceptions import NotFound, PermissionDenied, ValidationFailed
from app.core.permissions import Perm
from app.models.media import MediaAsset
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.media import (
    MediaRead,
    MediaUpdate,
    MediaUploadResult,
    SignedUploadRequest,
    SignedUploadResponse,
)
from app.services.storage import build_key, get_storage, probe_image, validate_upload

router = APIRouter(prefix="/media", tags=["media"])


# Where a file lands is picked by the caller, not free text — keeps
# "organize project media under /projects" from also being a path-traversal
# vector, since build_key() drops this straight into the storage key.
ALLOWED_UPLOAD_FOLDERS = {"uploads", "projects", "posts", "avatars", "services"}


@router.post("", response_model=MediaUploadResult, status_code=status.HTTP_201_CREATED)
async def upload(
    db: DbSession,
    user: Annotated[User, require(Perm.MEDIA_UPLOAD)],
    file: Annotated[UploadFile, File(description="The file to store")],
    alt_text: Annotated[str | None, Form()] = None,
    caption: Annotated[str | None, Form()] = None,
    labels: Annotated[str | None, Form(description="Comma separated")] = None,
    post_id: Annotated[int | None, Form()] = None,
    folder: Annotated[
        str, Form(description="Which subtree to file this under, e.g. 'projects'")
    ] = "uploads",
) -> MediaUploadResult:
    """Store one file and return the asset row the editor references."""
    if folder not in ALLOWED_UPLOAD_FOLDERS:
        raise ValidationFailed(
            f"'{folder}' isn't a recognised upload folder. "
            f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_FOLDERS))}."
        )

    raw = await file.read()
    content_type = validate_upload(
        file.filename or "upload", file.content_type or "", len(raw)
    )

    checksum = hashlib.sha256(raw).hexdigest()
    duplicate = await db.scalar(
        select(MediaAsset).where(
            MediaAsset.checksum == checksum,
            MediaAsset.owner_id == user.id,
            MediaAsset.deleted_at.is_(None),
        )
    )
    if duplicate is not None:
        return MediaUploadResult(asset=MediaRead.model_validate(duplicate), deduplicated=True)

    storage = get_storage()
    key = build_key(file.filename or "upload", prefix=folder)
    stored = storage.save(io.BytesIO(raw), key, content_type)

    asset = MediaAsset(
        storage_key=stored.storage_key,
        storage_backend=getattr(storage, "name", "local"),
        url=stored.url,
        original_filename=file.filename or "upload",
        content_type=content_type,
        kind=MediaAsset.kind_for(content_type),
        size_bytes=stored.size_bytes,
        checksum=stored.checksum,
        alt_text=alt_text,
        caption=caption,
        labels=[l.strip() for l in (labels or "").split(",") if l.strip()],
        owner_id=user.id,
        post_id=post_id,
    )

    # probe_image reads the file back off local disk, so it only makes sense
    # for the local backend — an S3-backed upload just skips width/height/
    # placeholder_color rather than crashing trying to open a path that was
    # never written locally.
    if asset.kind == "image" and getattr(storage, "name", "local") == "local":
        from app.core.config import settings

        for key_name, value in probe_image(Path(settings.MEDIA_ROOT) / stored.storage_key).items():
            setattr(asset, key_name, value)

    db.add(asset)
    await db.commit()
    await db.refresh(asset, ["owner"])
    return MediaUploadResult(asset=MediaRead.model_validate(asset))


@router.post("/signed-upload", response_model=SignedUploadResponse)
async def signed_upload(
    payload: SignedUploadRequest,
    _: Annotated[User, require(Perm.MEDIA_UPLOAD)],
) -> SignedUploadResponse:
    """Direct-to-storage upload for large video and audio.

    The local backend has no presign step, so this returns the normal upload
    route; switching to S3 or R2 makes it a real signed URL with no client
    change.
    """
    from app.core.config import settings

    validate_upload(payload.filename, payload.content_type, payload.size_bytes)
    key = build_key(payload.filename)
    storage = get_storage()
    try:
        signed = storage.presign_put(key, payload.content_type)
        return SignedUploadResponse(
            upload_url=signed["url"],
            headers=signed.get("headers", {}),
            storage_key=key,
            complete_url=f"{settings.API_V1_PREFIX}/media/complete",
        )
    except NotImplementedError:
        return SignedUploadResponse(
            upload_url=f"{settings.API_V1_PREFIX}/media",
            method="POST",
            storage_key=key,
            complete_url=f"{settings.API_V1_PREFIX}/media",
        )


@router.get("", response_model=Page[MediaRead])
async def list_media(
    db: DbSession,
    page: Pagination,
    user: Annotated[User, require(Perm.MEDIA_UPLOAD)],
    kind: str | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    mine: bool = False,
) -> Page[MediaRead]:
    stmt = select(MediaAsset).where(MediaAsset.deleted_at.is_(None))
    if mine or not user.has_permission(Perm.MEDIA_DELETE_ANY):
        stmt = stmt.where(MediaAsset.owner_id == user.id)
    if kind:
        stmt = stmt.where(MediaAsset.kind == kind)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                MediaAsset.original_filename.ilike(like),
                MediaAsset.alt_text.ilike(like),
                MediaAsset.caption.ilike(like),
            )
        )

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(MediaAsset.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
    ).all()
    return Page.build(
        [MediaRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
    )


@router.patch("/{asset_id}", response_model=MediaRead)
async def update_media(
    asset_id: int, payload: MediaUpdate, db: DbSession, user: CurrentUser
) -> MediaRead:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise NotFound("No file with that id.")
    if asset.owner_id != user.id and not user.has_permission(Perm.MEDIA_DELETE_ANY):
        raise PermissionDenied("You can only edit your own uploads.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)
    await db.commit()
    return MediaRead.model_validate(asset)


@router.delete("/{asset_id}", response_model=Message)
async def delete_media(asset_id: int, db: DbSession, user: CurrentUser) -> Message:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise NotFound("No file with that id.")

    owns = asset.owner_id == user.id
    if not (owns and user.has_permission(Perm.MEDIA_DELETE_OWN)) and not user.has_permission(
        Perm.MEDIA_DELETE_ANY
    ):
        raise PermissionDenied("You can only delete your own uploads.")

    if asset.reference_count > 0:
        # Keep the bytes; a post still points at them.
        asset.soft_delete()
        await db.commit()
        return Message(
            detail=f"Hidden from the library. {asset.reference_count} post(s) still use it.",
            code="soft_deleted",
        )

    get_storage().delete(asset.storage_key)
    await db.delete(asset)
    await db.commit()
    return Message(detail="File deleted.")
