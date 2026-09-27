"""Base schema classes, the pagination envelope and small shared shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Schema(BaseModel):
    """Request/response base. Rejects unknown keys so typos surface early."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ORMSchema(BaseModel):
    """Response base for objects read out of SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """Uniform list envelope used by every collection endpoint."""

    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def build(cls, items: list[T], total: int, page: int, per_page: int) -> "Page[T]":
        pages = max(1, -(-total // per_page)) if per_page else 1
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class PaginationParams(BaseModel):
    page: Annotated[int, Field(ge=1)] = 1
    per_page: Annotated[int, Field(ge=1, le=100)] = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class Message(BaseModel):
    """Simple acknowledgement body."""

    detail: str
    code: str = "ok"


class ErrorBody(BaseModel):
    code: str
    detail: str
    details: Any | None = None
    request_id: str | None = None


class Counter(BaseModel):
    label: str
    value: int
    change_pct: float | None = None


class TimeSeriesPoint(BaseModel):
    at: datetime
    value: float


class BulkIds(Schema):
    ids: Annotated[list[int], Field(min_length=1, max_length=200)]


class IdLabel(ORMSchema):
    id: int
    label: str
