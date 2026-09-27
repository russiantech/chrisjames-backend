"""Notification fan-out.

One call to :func:`notify` writes an in-app row, optionally queues an e-mail
and pushes onto the in-process event bus that the SSE endpoint streams from.
Preferences are consulted per recipient, per kind, per channel.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import NotificationChannel, NotificationKind
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.services.email import send_email

#: Which kinds default to an e-mail as well as an in-app row.
EMAIL_BY_DEFAULT: set[str] = {
    NotificationKind.POST_SUBMITTED,
    NotificationKind.POST_APPROVED,
    NotificationKind.POST_REJECTED,
    NotificationKind.REPLY_TO_COMMENT,
    NotificationKind.MENTION,
    NotificationKind.CONTACT_MESSAGE,
    NotificationKind.PROJECT_REQUEST,
    NotificationKind.PAYMENT_RECEIVED,
    NotificationKind.PAYMENT_FAILED,
}

ICONS: dict[str, tuple[str, str]] = {
    NotificationKind.COMMENT_ON_POST: ("bi-chat-left-text", "primary"),
    NotificationKind.REPLY_TO_COMMENT: ("bi-reply", "primary"),
    NotificationKind.MENTION: ("bi-at", "info"),
    NotificationKind.REACTION: ("bi-heart", "danger"),
    NotificationKind.POST_SUBMITTED: ("bi-inbox", "warning"),
    NotificationKind.POST_APPROVED: ("bi-check-circle", "success"),
    NotificationKind.POST_REJECTED: ("bi-x-circle", "danger"),
    NotificationKind.POST_PUBLISHED: ("bi-megaphone", "success"),
    NotificationKind.COMMENT_FLAGGED: ("bi-flag", "warning"),
    NotificationKind.CONTACT_MESSAGE: ("bi-envelope", "primary"),
    NotificationKind.PROJECT_REQUEST: ("bi-briefcase", "warning"),
    NotificationKind.PAYMENT_RECEIVED: ("bi-credit-card", "success"),
    NotificationKind.PAYMENT_FAILED: ("bi-credit-card", "danger"),
    NotificationKind.AD_APPROVED: ("bi-badge-ad", "success"),
    NotificationKind.AD_EXPIRING: ("bi-hourglass-split", "warning"),
    NotificationKind.NEWSLETTER: ("bi-send", "info"),
    NotificationKind.SYSTEM: ("bi-bell", "secondary"),
}


class EventBus:
    """Per-user asyncio fan-out backing the SSE stream.

    Single-process by design. Behind more than one worker, swap the two
    ``publish``/``subscribe`` bodies for Redis pub/sub — nothing else changes.
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[str]]] = defaultdict(set)

    def subscribe(self, user_id: int) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: int, queue: asyncio.Queue[str]) -> None:
        self._subscribers.get(user_id, set()).discard(queue)
        if not self._subscribers.get(user_id):
            self._subscribers.pop(user_id, None)

    def publish(self, user_id: int, event: str, payload: dict[str, Any]) -> None:
        message = f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
        for queue in list(self._subscribers.get(user_id, ())):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # A stalled client must never block the request that notified.
                pass

    def listener_count(self, user_id: int) -> int:
        return len(self._subscribers.get(user_id, ()))


bus = EventBus()


async def _channel_enabled(
    db: AsyncSession, user_id: int, kind: str, channel: str, default: bool
) -> bool:
    row = await db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.kind == kind,
            NotificationPreference.channel == channel,
        )
    )
    return row.enabled if row is not None else default


async def notify(
    db: AsyncSession,
    *,
    recipient: User | int,
    kind: NotificationKind | str,
    title: str,
    body: str | None = None,
    url: str | None = None,
    actor: User | None = None,
    subject_type: str | None = None,
    subject_id: int | None = None,
    payload: dict[str, Any] | None = None,
    group_key: str | None = None,
    email_template: str | None = None,
    email_context: dict[str, Any] | None = None,
) -> Notification | None:
    """Create one notification for one recipient.

    Returns ``None`` when the recipient has muted the in-app channel or is
    notifying themselves.
    """
    recipient_id = recipient if isinstance(recipient, int) else recipient.id
    if actor is not None and actor.id == recipient_id:
        return None

    kind = str(kind)
    icon, accent = ICONS.get(kind, ("bi-bell", "primary"))

    if not await _channel_enabled(
        db, recipient_id, kind, NotificationChannel.IN_APP, default=True
    ):
        notification = None
    else:
        notification = None
        if group_key:
            # Collapse repeats rather than stacking near-identical rows.
            existing = await db.scalar(
                select(Notification).where(
                    Notification.recipient_id == recipient_id,
                    Notification.group_key == group_key,
                    Notification.read_at.is_(None),
                )
            )
            if existing is not None:
                existing.group_count += 1
                existing.title = title
                existing.created_at = datetime.now(timezone.utc)
                notification = existing

        if notification is None:
            notification = Notification(
                recipient_id=recipient_id,
                actor_id=actor.id if actor else None,
                kind=kind,
                title=title[:220],
                body=body,
                url=url,
                icon=icon,
                accent=accent,
                subject_type=subject_type,
                subject_id=subject_id,
                payload=payload or {},
                group_key=group_key,
            )
            db.add(notification)
        await db.flush()

        bus.publish(
            recipient_id,
            "notification",
            {
                "id": notification.id,
                "kind": kind,
                "title": notification.title,
                "body": body,
                "url": url,
                "icon": icon,
                "accent": accent,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    wants_email = kind in EMAIL_BY_DEFAULT
    if email_template and await _channel_enabled(
        db, recipient_id, kind, NotificationChannel.EMAIL, default=wants_email
    ):
        user = (
            recipient
            if isinstance(recipient, User)
            else await db.get(User, recipient_id)
        )
        if user is not None and user.email:
            await send_email(
                db,
                to_address=user.email,
                template=email_template,
                context={
                    "name": user.display_name,
                    "action_url": f"{settings.SITE_URL}{url or ''}",
                    **(email_context or {}),
                },
            )
    return notification


async def notify_many(
    db: AsyncSession, *, recipients: list[User], **kwargs: Any
) -> list[Notification]:
    created = []
    for recipient in recipients:
        result = await notify(db, recipient=recipient, **kwargs)
        if result is not None:
            created.append(result)
    return created


async def notify_permission_holders(
    db: AsyncSession, permission: str, **kwargs: Any
) -> list[Notification]:
    """Notify every active account that holds ``permission`` — the staff inbox."""
    users = (await db.scalars(select(User).where(User.status == "active"))).all()
    targets = [u for u in users if u.has_permission(permission)]
    return await notify_many(db, recipients=targets, **kwargs)


async def counts_for(db: AsyncSession, user_id: int) -> dict[str, Any]:
    total = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id, Notification.archived_at.is_(None)
        )
    )
    unread = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.read_at.is_(None),
            Notification.archived_at.is_(None),
        )
    )
    unseen = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.seen_at.is_(None),
            Notification.archived_at.is_(None),
        )
    )
    by_kind_rows = await db.execute(
        select(Notification.kind, func.count(Notification.id))
        .where(
            Notification.recipient_id == user_id,
            Notification.read_at.is_(None),
            Notification.archived_at.is_(None),
        )
        .group_by(Notification.kind)
    )
    return {
        "total": total or 0,
        "unread": unread or 0,
        "unseen": unseen or 0,
        "by_kind": {kind: count for kind, count in by_kind_rows.all()},
    }


async def mark_read(
    db: AsyncSession, user_id: int, ids: list[int] | None, read: bool = True
) -> int:
    stmt = update(Notification).where(Notification.recipient_id == user_id)
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    else:
        stmt = stmt.where(Notification.read_at.is_(None))
    now = datetime.now(timezone.utc)
    result = await db.execute(
        stmt.values(read_at=now if read else None, seen_at=now)
    )
    return result.rowcount or 0
