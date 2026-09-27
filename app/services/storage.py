"""File storage.

A small backend interface with a local-disk implementation. Swapping in S3,
R2 or Spaces means implementing :class:`StorageBackend` and changing one line
in :func:`get_storage`; nothing above this module knows which one is active.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import ValidationFailed

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass(slots=True)
class StoredFile:
    storage_key: str
    url: str
    size_bytes: int
    checksum: str
    content_type: str
    original_filename: str


def safe_filename(name: str) -> str:
    stem = Path(name).stem[:80]
    suffix = Path(name).suffix[:12]
    return f"{_SAFE_NAME.sub('-', stem).strip('-') or 'file'}{_SAFE_NAME.sub('', suffix)}"


def build_key(filename: str, prefix: str = "uploads") -> str:
    today = datetime.now(timezone.utc)
    return (
        f"{prefix}/{today:%Y/%m}/{uuid.uuid4().hex[:12]}-{safe_filename(filename)}"
    )


class StorageBackend(ABC):
    @abstractmethod
    def save(self, fileobj: BinaryIO, key: str, content_type: str) -> StoredFile: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...

    def presign_put(self, key: str, content_type: str, expires: int = 900) -> dict:
        """Direct-to-storage upload. Local disk has no equivalent."""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    name = "local"

    def __init__(self, root: Path | None = None, base_url: str | None = None) -> None:
        self.root = Path(root or settings.MEDIA_ROOT)
        self.base_url = (base_url or settings.MEDIA_URL).rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        # Refuse anything that escapes the media root.
        if not str(target).startswith(str(self.root.resolve())):
            raise ValidationFailed("That file path is not allowed.")
        return target

    def save(self, fileobj: BinaryIO, key: str, content_type: str) -> StoredFile:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with path.open("wb") as out:
            while chunk := fileobj.read(1024 * 256):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
        return StoredFile(
            storage_key=key,
            url=self.url_for(key),
            size_bytes=size,
            checksum=digest.hexdigest(),
            content_type=content_type,
            original_filename=Path(key).name,
        )

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def url_for(self, key: str) -> str:
        return f"{self.base_url}/{key}"

    def copy(self, key: str, new_key: str) -> str:
        destination = self._path(new_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._path(key), destination)
        return self.url_for(new_key)


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def validate_upload(filename: str, content_type: str, size_bytes: int) -> str:
    """Check type and size, returning the content type to record."""
    content_type = (content_type or "").split(";")[0].strip().lower()
    if not content_type or content_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(filename)
        content_type = guessed or "application/octet-stream"

    if content_type not in settings.ALLOWED_UPLOAD_TYPES:
        allowed = ", ".join(sorted({t.split("/")[0] for t in settings.ALLOWED_UPLOAD_TYPES}))
        raise ValidationFailed(
            f"{content_type} files are not accepted. Allowed kinds: {allowed}.",
            details={"content_type": content_type},
        )

    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if size_bytes > limit:
        raise ValidationFailed(
            f"That file is {size_bytes / 1_048_576:.1f} MB. The limit is "
            f"{settings.MAX_UPLOAD_MB} MB.",
            details={"max_mb": settings.MAX_UPLOAD_MB},
        )
    return content_type


def probe_image(path: Path) -> dict:
    """Pull dimensions and a dominant colour, when Pillow is installed."""
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:  # pragma: no cover - Pillow is optional
        return {}
    try:
        with Image.open(path) as image:
            width, height = image.size
            thumbnail = image.convert("RGB").resize((1, 1))
            r, g, b = thumbnail.getpixel((0, 0))
        return {
            "width": width,
            "height": height,
            "placeholder_color": f"#{r:02x}{g:02x}{b:02x}",
        }
    except Exception:
        return {}
