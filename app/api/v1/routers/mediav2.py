"""Media: upload a file directly, or attach one by link — same result either way.

Both routes return the same ``MediaOut`` shape, so the editor doesn't care
which one a person used. See the two "ADAPT THIS" notes below before wiring
this in — everything else follows the same shape as ``app/api/posts.py``.

ADAPT THIS (1) — permission: reusing ``Perm.POST_CREATE`` since media is
always attached to a post/block. Swap in a dedicated ``Perm.MEDIA_UPLOAD``
if you have (or want) one.

ADAPT THIS (2) — ``MediaAsset`` columns: constructing it via
``_mapped_kwargs`` below only passes through kwargs that are actually
columns on your model, so this won't crash if your column names differ —
but the response always reflects what THIS request actually did (the real
URL, the real size), even for any field your model happens not to have.
Check the shape of your ``MediaAsset`` and adjust ``candidate`` if you'd
rather it fail loudly on a mismatch instead.

WIRING
------
1. Register the router the same way posts.router is registered, e.g. in
   app/main.py: ``app.include_router(media.router)``
2. Serve MEDIA_ROOT as static files, e.g.:
       from fastapi.staticfiles import StaticFiles
       app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")
   (adjust MEDIA_ROOT below to match wherever you actually want uploads to
   live — a mounted volume in production, most likely).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, UploadFile

from app.api.deps import DbSession, require
from app.core.exceptions import ValidationFailed
from app.core.permissions import Perm
from app.models.media import MediaAsset
from app.models.user import User
from app.schemas.media import MediaKind, MediaLinkIn, MediaOut

router = APIRouter(prefix="/media", tags=["media"])

MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "media")).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 50 * 1024 * 1024))  # 50 MB

# "Any valid different media format" still means an allow-list, not a free-for-all —
# arbitrary uploads (.exe, .php, .sh, …) are a real risk on a server that can execute
# things. Add extensions here if something legitimate is missing.
ALLOWED_EXTENSIONS: dict[MediaKind, set[str]] = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".bmp"},
    "video": {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"},
    "audio": {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"},
    "document": {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".csv", ".zip"},
}


def _kind_for_extension(ext: str) -> MediaKind:
    ext = ext.lower()
    for kind, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return kind
    return "other"


def _mapped_kwargs(model: type, candidate: dict[str, Any]) -> dict[str, Any]:
    """Only the keys that are actually columns on `model` — see ADAPT THIS (2)."""
    return {key: value for key, value in candidate.items() if hasattr(model, key)}


# ------------------------------------------------------------------- upload
@router.post("/upload", response_model=MediaOut, status_code=201)
async def upload_media(
    db: DbSession,
    file: UploadFile,
    user: Annotated[User, require(Perm.POST_CREATE)],  # ADAPT THIS (1)
) -> MediaOut:
    original_name = file.filename or "upload"
    ext = Path(original_name).suffix.lower()
    kind = _kind_for_extension(ext)
    if kind == "other" and ext:
        allowed = ", ".join(sorted({e for exts in ALLOWED_EXTENSIONS.values() for e in exts}))
        raise ValidationFailed(f"'{ext}' isn't an accepted file type. Allowed: {allowed}")

    dest_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = MEDIA_ROOT / dest_name

    size = 0
    try:
        with dest_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise ValidationFailed(
                        f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
                    )
                buffer.write(chunk)
    except ValidationFailed:
        dest_path.unlink(missing_ok=True)
        raise
    except Exception:
        dest_path.unlink(missing_ok=True)
        raise

    url = f"/media/{dest_name}"

    candidate = {
        "url": url,
        "filename": original_name,
        "content_type": file.content_type,
        "size_bytes": size,
        "kind": kind,
        "uploaded_by_id": user.id,
        "source": "upload",
    }
    media = MediaAsset(**_mapped_kwargs(MediaAsset, candidate))
    db.add(media)
    await db.commit()
    await db.refresh(media)

    return MediaOut(
        id=media.id,
        url=getattr(media, "url", url),
        kind=getattr(media, "kind", kind),
        filename=getattr(media, "filename", original_name),
        content_type=getattr(media, "content_type", file.content_type),
        size_bytes=getattr(media, "size_bytes", size),
    )


# --------------------------------------------------------------------- link
@router.post("/link", response_model=MediaOut, status_code=201)
async def attach_media_link(
    payload: MediaLinkIn,
    db: DbSession,
    user: Annotated[User, require(Perm.POST_CREATE)],  # ADAPT THIS (1)
) -> MediaOut:
    """Reference an already-hosted file by URL — nothing is downloaded or
    re-hosted, only best-effort inspected for its kind/size."""
    url = str(payload.url)
    ext = Path(url.split("?")[0]).suffix.lower()
    kind = _kind_for_extension(ext)
    content_type: str | None = None
    size_bytes: int | None = None

    # Best-effort only: a HEAD request with no redirect-following, short
    # timeout, and a failure that's silently ignored rather than surfaced —
    # this is metadata for the editor's UI, not something worth blocking on.
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=5) as client:
            head = await client.head(url)
        content_type = head.headers.get("content-type")
        content_length = head.headers.get("content-length")
        size_bytes = int(content_length) if content_length else None
        if kind == "other" and content_type:
            if content_type.startswith("image/"):
                kind = "image"
            elif content_type.startswith("video/"):
                kind = "video"
            elif content_type.startswith("audio/"):
                kind = "audio"
    except Exception:
        pass

    candidate = {
        "url": url,
        "filename": Path(url.split("?")[0]).name or None,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "kind": kind,
        "uploaded_by_id": user.id,
        "source": "link",
    }
    media = MediaAsset(**_mapped_kwargs(MediaAsset, candidate))
    db.add(media)
    await db.commit()
    await db.refresh(media)

    return MediaOut(
        id=media.id,
        url=getattr(media, "url", url),
        kind=getattr(media, "kind", kind),
        filename=getattr(media, "filename", candidate["filename"]),
        content_type=getattr(media, "content_type", content_type),
        size_bytes=getattr(media, "size_bytes", size_bytes),
    )
