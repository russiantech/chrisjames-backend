"""Notification inbox, preferences and the live stream."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, Pagination
from app.core.exceptions import NotFound
from app.models.notification import Notification, NotificationPreference
from app.schemas.common import Message, Page
from app.schemas.notification import (
    NotificationCounts,
    NotificationMarkIn,
    NotificationRead,
    PreferenceBulkIn,
    PreferenceRead,
)
from app.services import notifications as service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationRead])
async def inbox(
    db: DbSession,
    user: CurrentUser,
    page: Pagination,
    unread_only: Annotated[bool, Query(alias="unreadOnly")] = False,
    kind: str | None = None,
) -> Page[NotificationRead]:
    stmt = select(Notification).where(
        Notification.recipient_id == user.id, Notification.archived_at.is_(None)
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if kind:
        stmt = stmt.where(Notification.kind == kind)

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(Notification.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
    ).unique().all()
    return Page.build(
        [NotificationRead.model_validate(row) for row in rows],
        total or 0,
        page.page,
        page.per_page,
    )


@router.get("/counts", response_model=NotificationCounts)
async def counts(db: DbSession, user: CurrentUser) -> NotificationCounts:
    return NotificationCounts(**await service.counts_for(db, user.id))


@router.post("/read", response_model=Message)
async def mark(payload: NotificationMarkIn, db: DbSession, user: CurrentUser) -> Message:
    changed = await service.mark_read(db, user.id, payload.ids, payload.read)
    await db.commit()
    return Message(detail=f"{changed} notification(s) updated.")


@router.delete("/{notification_id}", response_model=Message)
async def archive(notification_id: int, db: DbSession, user: CurrentUser) -> Message:
    row = await db.get(Notification, notification_id)
    if row is None or row.recipient_id != user.id:
        raise NotFound("No notification with that id.")
    from datetime import datetime, timezone

    row.archived_at = datetime.now(timezone.utc)
    await db.commit()
    return Message(detail="Archived.")


@router.get("/stream")
async def stream(request: Request, user: CurrentUser) -> StreamingResponse:
    """Server-sent events. One long-lived connection per open tab.

    A heartbeat every 25 seconds keeps proxies from closing an idle stream.
    """
    queue = service.bus.subscribe(user.id)

    async def events():
        try:
            yield 'event: ready\ndata: {"ok":true}\n\n'
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=25)
                    yield message
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            service.bus.unsubscribe(user.id, queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/preferences", response_model=list[PreferenceRead])
async def read_preferences(db: DbSession, user: CurrentUser) -> list[NotificationPreference]:
    rows = await db.scalars(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    return list(rows.all())


@router.put("/preferences", response_model=list[PreferenceRead])
async def write_preferences(
    payload: PreferenceBulkIn, db: DbSession, user: CurrentUser
) -> list[NotificationPreference]:
    for item in payload.preferences:
        row = await db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user.id,
                NotificationPreference.kind == item.kind,
                NotificationPreference.channel == item.channel,
            )
        )
        if row is None:
            row = NotificationPreference(
                user_id=user.id, kind=item.kind, channel=item.channel
            )
            db.add(row)
        row.enabled = item.enabled
        row.digest = item.digest
    await db.commit()

    rows = await db.scalars(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    return list(rows.all())
