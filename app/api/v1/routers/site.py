"""Site settings, search, analytics and the dashboard overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbSession, MaybeUser, require
from app.core.config import settings as env
from app.core.permissions import Perm
from app.models.comment import Comment
from app.models.enums import (
    MessageStatus,
    ModerationState,
    PostStatus,
    RequestStatus,
)
from app.models.inbox import ContactMessage, NewsletterSubscriber, ProjectRequest
from app.models.payment import Payment
from app.models.portfolio import Project, SiteSetting
from app.models.post import Post, PostView
from app.models.user import User
from app.schemas.common import Message
from app.schemas.portfolio import ProjectSummary
from app.schemas.post import PostSummary
from app.services import posts as post_service, settings_store
from app.services.text import pygments_stylesheet

router = APIRouter(tags=["site"])


@router.get("/settings/public")
async def public_settings(db: DbSession) -> dict[str, Any]:
    """Everything the unauthenticated client needs to configure itself."""
    values = await settings_store.public_settings(db)
    return {
        **values,
        "owner_name_short": env.OWNER_NAME_SHORT,
        "owner_name": env.OWNER_NAME,
        "owner_email": env.OWNER_EMAIL,
        "currency": env.DEFAULT_CURRENCY,
        "max_upload_mb": env.MAX_UPLOAD_MB,
        "payment_provider": env.PAYMENT_PROVIDER,
    }


@router.get("/settings")
async def all_settings(
    db: DbSession, _: Annotated[User, require(Perm.SETTINGS_MANAGE)]
) -> list[dict[str, Any]]:
    stored = {
        row.key: row
        for row in (await db.scalars(select(SiteSetting))).all()
    }
    out = []
    for key, (env_attr, value_type, group, label, is_public) in settings_store.DEFINITIONS.items():
        row = stored.get(key)
        value = (
            row.value
            if row is not None
            else (
                getattr(env, env_attr)
                if env_attr and hasattr(env, env_attr)
                else settings_store.DEFAULTS.get(key)
            )
        )
        out.append(
            {
                "key": key,
                "value": value,
                "value_type": value_type,
                "group": group,
                "label": label,
                "is_public": is_public,
                "is_overridden": row is not None,
            }
        )
    return out


@router.put("/settings", response_model=Message)
async def write_settings(
    payload: dict[str, Any],
    db: DbSession,
    _: Annotated[User, require(Perm.SETTINGS_MANAGE)],
) -> Message:
    unknown = set(payload) - set(settings_store.DEFINITIONS)
    if unknown:
        return Message(
            detail=f"Ignored unknown settings: {', '.join(sorted(unknown))}.",
            code="partial",
        )
    for key, value in payload.items():
        await settings_store.set_setting(db, key, value)
    await db.commit()
    return Message(detail=f"{len(payload)} setting(s) saved.")


@router.get("/search")
async def search(
    db: DbSession,
    user: MaybeUser,
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: int = 8,
) -> dict[str, Any]:
    """One search box across posts and projects."""
    limit = min(limit, 20)

    post_rows = (
        await db.scalars(
            post_service.base_query()
            .where(post_service.visible_filter(user), post_service.search_filter(q))
            .order_by(Post.published_at.desc().nullslast())
            .limit(limit)
        )
    ).unique().all()

    like = f"%{q}%"
    project_rows = (
        await db.scalars(
            select(Project)
            .where(
                Project.is_published.is_(True),
                (Project.title.ilike(like)) | (Project.summary.ilike(like)),
            )
            .limit(limit)
        )
    ).all()

    return {
        "query": q,
        "posts": [PostSummary.model_validate(row).model_dump() for row in post_rows],
        "projects": [ProjectSummary.model_validate(row).model_dump() for row in project_rows],
    }


@router.get("/dashboard/overview")
async def dashboard_overview(
    db: DbSession, _: Annotated[User, require(Perm.ANALYTICS_READ)]
) -> dict[str, Any]:
    """Counters and a 30-day view series for the dashboard home."""
    since = datetime.now(timezone.utc) - timedelta(days=30)

    async def count(model, *conditions) -> int:
        return (await db.scalar(select(func.count(model.id)).where(*conditions))) or 0

    views_rows = await db.execute(
        select(func.date(PostView.created_at), func.count(PostView.id))
        .where(PostView.created_at >= since)
        .group_by(func.date(PostView.created_at))
        .order_by(func.date(PostView.created_at))
    )

    revenue = (
        await db.scalar(
            select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                Payment.status == "succeeded", Payment.created_at >= since
            )
        )
    ) or 0

    return {
        "counters": {
            "published_posts": await count(Post, Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None)),
            "awaiting_review": await count(Post, Post.status == PostStatus.SUBMITTED),
            "draft_posts": await count(Post, Post.status == PostStatus.DRAFT),
            "comments_pending": await count(Comment, Comment.moderation_state == ModerationState.PENDING),
            "unread_messages": await count(ContactMessage, ContactMessage.status == MessageStatus.UNREAD),
            "open_requests": await count(ProjectRequest, ProjectRequest.status == RequestStatus.NEW),
            "subscribers": await count(NewsletterSubscriber, NewsletterSubscriber.status == "subscribed"),
            "members": await count(User, User.deleted_at.is_(None)),
        },
        "revenue_30d_minor": int(revenue),
        "views_30d": [
            {"date": str(day), "value": value} for day, value in views_rows.all()
        ],
    }


@router.get("/analytics/posts")
async def post_analytics(
    db: DbSession,
    _: Annotated[User, require(Perm.ANALYTICS_READ)],
    days: int = 30,
    limit: int = 10,
) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 365))
    rows = await db.execute(
        select(
            Post.id,
            Post.title,
            Post.slug,
            func.count(PostView.id).label("views"),
            func.coalesce(func.avg(PostView.scroll_depth), 0).label("avg_scroll"),
            func.coalesce(func.avg(PostView.seconds_on_page), 0).label("avg_seconds"),
        )
        .join(PostView, PostView.post_id == Post.id)
        .where(PostView.created_at >= since)
        .group_by(Post.id)
        .order_by(func.count(PostView.id).desc())
        .limit(min(limit, 50))
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "slug": row.slug,
            "views": row.views,
            "avg_scroll_depth": round(float(row.avg_scroll), 1),
            "avg_seconds_on_page": round(float(row.avg_seconds), 1),
        }
        for row in rows.all()
    ]


@router.get("/code-theme.css")
async def code_theme() -> Any:
    """Pygments stylesheet, served so the client needs no build-time copy."""
    from fastapi.responses import Response

    return Response(
        pygments_stylesheet(),
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=86400"},
    )
