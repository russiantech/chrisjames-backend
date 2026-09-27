"""Blog posts: the public feed, authoring, review and reactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    AnonKey,
    CurrentUser,
    DbSession,
    MaybeUser,
    Pagination,
    client_ip,
    require,
)
from app.core.exceptions import NotFound, PermissionDenied, ValidationFailed
from app.core.permissions import Perm
from app.models.enums import NotificationKind, PostStatus
from app.models.poll import Poll
from app.models.post import Bookmark, Post, PostReaction, PostView
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.post import (
    PostCreate,
    PostDetail,
    PostGuestCreate,
    PostModerationDecision,
    PostReactionIn,
    PostStatusChange,
    PostSummary,
    PostUpdate,
    PostViewIn,
    ReactionSummary,
)
from app.services import notifications, posts as service, settings_store
from app.services.polls import decorate_poll

router = APIRouter(prefix="/posts", tags=["posts"])

SortKey = Literal["recent", "popular", "trending", "oldest", "commented"]

_SORTS = {
    "recent": (Post.published_at.desc().nullslast(), Post.created_at.desc()),
    "oldest": (Post.published_at.asc().nullsfirst(),),
    "popular": (Post.view_count.desc(), Post.published_at.desc().nullslast()),
    "trending": (Post.trending_score.desc(), Post.published_at.desc().nullslast()),
    "commented": (Post.comment_count.desc(), Post.published_at.desc().nullslast()),
}


async def _decorate(
    db: DbSession, post: Post, user: User | None, anon: str
) -> PostDetail:
    # Everything below is serialised, so it must be in memory first — an
    # implicit lazy load during serialisation would fail under the async engine.
    await service.ensure_loaded(db, post, "polls", "blocks", "tags", "series")

    detail = PostDetail.model_validate(post)
    detail.byline = post.byline
    detail.can_edit = service.can_edit(post, user)
    detail.can_delete = service.can_delete(post, user)
    detail.can_moderate = bool(user and user.has_permission(Perm.POST_MODERATE))

    reaction = await db.scalar(
        select(PostReaction).where(
            PostReaction.post_id == post.id,
            PostReaction.user_id == user.id if user else PostReaction.anon_key == anon,
        )
    )
    detail.my_reaction = reaction.type if reaction else None

    if user is not None:
        detail.is_bookmarked = (
            await db.scalar(
                select(Bookmark.id).where(
                    Bookmark.post_id == post.id, Bookmark.user_id == user.id
                )
            )
        ) is not None

    detail.polls = [await decorate_poll(db, poll, user, anon) for poll in post.polls]
    return detail


# --------------------------------------------------------------------- read
@router.get("", response_model=Page[PostSummary])
async def list_posts(
    db: DbSession,
    user: MaybeUser,
    page: Pagination,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    series: str | None = None,
    featured: bool | None = None,
    post_status: Annotated[str | None, Query(alias="status")] = None,
    sort: SortKey = "recent",
) -> Page[PostSummary]:
    """The feed. Drafts and submissions appear only for those allowed to see them."""
    stmt = service.base_query().where(service.visible_filter(user))

    if q:
        stmt = stmt.where(service.search_filter(q))
    if category:
        from app.models.taxonomy import Category

        stmt = stmt.join(Category, Post.category_id == Category.id).where(
            Category.slug == category
        )
    if tag:
        from app.models.taxonomy import Tag

        stmt = stmt.join(Post.tags).where(Tag.slug == tag)
    if author:
        stmt = stmt.join(User, Post.author_id == User.id).where(User.username == author)
    if series:
        from app.models.taxonomy import Series

        stmt = stmt.join(Series, Post.series_id == Series.id).where(Series.slug == series)
    if featured is not None:
        stmt = stmt.where(Post.is_featured.is_(featured))
    if post_status:
        if not (user and user.has_permission(Perm.POST_READ_DRAFT)):
            raise PermissionDenied("Filtering by status needs review access.")
        stmt = stmt.where(Post.status == post_status)

    total = await db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    )
    stmt = stmt.order_by(Post.is_pinned.desc(), *_SORTS[sort])
    rows = (await db.scalars(stmt.offset(page.offset).limit(page.limit))).unique().all()

    items = []
    for row in rows:
        summary = PostSummary.model_validate(row)
        summary.byline = row.byline
        items.append(summary)
    return Page.build(items, total or 0, page.page, page.per_page)


@router.get("/featured", response_model=list[PostSummary])
async def featured_posts(db: DbSession, user: MaybeUser, limit: int = 3) -> list[PostSummary]:
    rows = (
        await db.scalars(
            service.base_query()
            .where(service.visible_filter(user), Post.is_featured.is_(True))
            .order_by(Post.published_at.desc().nullslast())
            .limit(min(limit, 12))
        )
    ).unique().all()
    return [PostSummary.model_validate(row) for row in rows]


@router.get("/{slug}", response_model=PostDetail)
async def read_post(
    slug: str, db: DbSession, user: MaybeUser, anon: AnonKey
) -> PostDetail:
    post = await service.get_by_slug_or_404(db, slug)
    if not service.can_view(post, user):
        # 404 rather than 403, so private slugs stay unguessable.
        raise NotFound("No post with that address.")
    return await _decorate(db, post, user, anon)


@router.get("/{slug}/related", response_model=list[PostSummary])
async def related_posts(
    slug: str, db: DbSession, user: MaybeUser, limit: int = 3
) -> list[PostSummary]:
    """Same category first, then anything sharing a tag."""
    post = await service.get_by_slug_or_404(db, slug)
    tag_ids = [tag.id for tag in post.tags]

    stmt = (
        service.base_query()
        .where(service.visible_filter(user), Post.id != post.id)
        .limit(min(limit, 10))
    )
    if post.category_id:
        stmt = stmt.where(Post.category_id == post.category_id)
    rows = (await db.scalars(stmt.order_by(Post.published_at.desc().nullslast()))).unique().all()

    if len(rows) < limit and tag_ids:
        from app.models.taxonomy import Tag

        extra = (
            await db.scalars(
                service.base_query()
                .join(Post.tags)
                .where(
                    service.visible_filter(user),
                    Post.id != post.id,
                    Tag.id.in_(tag_ids),
                )
                .limit(limit)
            )
        ).unique().all()
        seen = {row.id for row in rows}
        rows = list(rows) + [row for row in extra if row.id not in seen]

    return [PostSummary.model_validate(row) for row in rows[:limit]]


# -------------------------------------------------------------------- write
@router.post("", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    db: DbSession,
    anon: AnonKey,
    user: Annotated[User, require(Perm.POST_CREATE)],
) -> PostDetail:
    target = await service.resolve_target_status(db, payload.status, user)

    post = Post(
        title=payload.title,
        slug=await service.unique_slug(db, payload.slug or payload.title),
        subtitle=payload.subtitle,
        excerpt=payload.excerpt,
        cover_url=payload.cover_url,
        cover_caption=payload.cover_caption,
        category_id=payload.category_id,
        series_id=payload.series_id,
        series_position=payload.series_position,
        visibility=payload.visibility,
        allow_comments=payload.allow_comments,
        allow_reactions=payload.allow_reactions,
        show_ads=payload.show_ads,
        layout_options=payload.layout_options,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        canonical_url=payload.canonical_url,
        og_image_url=payload.og_image_url,
        language=payload.language,
        author_id=user.id,
        status=PostStatus.DRAFT,
    )
    db.add(post)
    await db.flush()

    await service.sync_tags(db, post, payload.tags)
    await service.sync_blocks(db, post, payload.blocks)
    await service.snapshot(db, post, user, "Created")
    await service.apply_status(
        db, post, target, actor=user, scheduled_for=payload.scheduled_for
    )
    await db.commit()
    await db.refresh(post)
    return await _decorate(db, post, user, anon)


@router.post("/submit", response_model=Message, status_code=status.HTTP_201_CREATED)
async def submit_as_guest(
    payload: PostGuestCreate, request: Request, db: DbSession
) -> Message:
    """A post from a visitor with no account. Always goes through review
    unless the auto-publish switch is on."""
    if not await settings_store.get_setting(db, "guest_posts_enabled", True):
        raise PermissionDenied("Guest submissions are closed at the moment.")

    post = Post(
        title=payload.title,
        slug=await service.unique_slug(db, payload.title),
        subtitle=payload.subtitle,
        excerpt=payload.excerpt,
        cover_url=payload.cover_url,
        category_id=payload.category_id,
        visibility=payload.visibility,
        guest_name=payload.guest_name,
        guest_email=payload.guest_email.lower(),
        byline_override=payload.byline_override,
        status=PostStatus.DRAFT,
        language=payload.language,
    )
    db.add(post)
    await db.flush()

    await service.sync_tags(db, post, payload.tags)
    await service.sync_blocks(db, post, payload.blocks)

    auto = await settings_store.get_setting(db, "auto_publish_submissions", False)
    await service.apply_status(
        db, post, PostStatus.PUBLISHED if auto else PostStatus.SUBMITTED
    )
    await db.commit()

    return Message(
        detail=(
            "Your post is live. Thanks for contributing."
            if auto
            else "Thanks — your post is in the review queue. You will hear back by e-mail."
        ),
        code="published" if auto else "submitted",
    )


@router.patch("/{slug}", response_model=PostDetail)
async def update_post(
    slug: str,
    payload: PostUpdate,
    db: DbSession,
    user: CurrentUser,
    anon: AnonKey,
) -> PostDetail:
    """Edited by slug, the same address the reader and the editor both see."""
    post = await db.scalar(service.base_query().where(Post.slug == slug))
    if post is None:
        raise NotFound("No post at that address.")
    service.require_edit(post, user)

    if payload.blocks is not None:
        await service.snapshot(db, post, user, payload.change_note)

    fields = payload.model_dump(exclude_unset=True, exclude={"tags", "blocks", "change_note", "slug"})
    for key, value in fields.items():
        setattr(post, key, value)

    if payload.slug and payload.slug != post.slug:
        post.slug = await service.unique_slug(db, payload.slug, post_id=post.id)
    if payload.tags is not None:
        await service.sync_tags(db, post, payload.tags)
    if payload.blocks is not None:
        await service.sync_blocks(db, post, payload.blocks)

    await db.commit()
    await db.refresh(post)
    return await _decorate(db, post, user, anon)


@router.post("/{slug}/status", response_model=PostDetail)
async def change_status(
    slug: str,
    payload: PostStatusChange,
    db: DbSession,
    user: CurrentUser,
    anon: AnonKey,
) -> PostDetail:
    post = await db.scalar(service.base_query().where(Post.slug == slug))
    if post is None:
        raise NotFound("No post at that address.")
    service.require_edit(post, user)

    target = await service.resolve_target_status(db, payload.status, user)
    await service.apply_status(
        db,
        post,
        target,
        actor=user,
        reason=payload.reason,
        scheduled_for=payload.scheduled_for,
    )
    await db.commit()
    await db.refresh(post)
    return await _decorate(db, post, user, anon)


@router.delete("/{slug}", response_model=Message)
async def delete_post(slug: str, db: DbSession, user: CurrentUser) -> Message:
    post = await db.scalar(select(Post).where(Post.slug == slug))
    if post is None:
        raise NotFound("No post at that address.")
    if not service.can_delete(post, user):
        raise PermissionDenied("You can only delete your own posts.")
    post.soft_delete()
    await db.commit()
    return Message(detail="Post moved to the bin. An editor can restore it.")


# --------------------------------------------------------------- moderation
@router.get("/review/queue", response_model=Page[PostSummary])
async def review_queue(
    db: DbSession,
    page: Pagination,
    _: Annotated[User, require(Perm.POST_MODERATE)],
) -> Page[PostSummary]:
    stmt = service.base_query().where(
        Post.status == PostStatus.SUBMITTED, Post.deleted_at.is_(None)
    )
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(Post.submitted_at.asc()).offset(page.offset).limit(page.limit)
        )
    ).unique().all()
    items = []
    for row in rows:
        summary = PostSummary.model_validate(row)
        summary.byline = row.byline
        items.append(summary)
    return Page.build(items, total or 0, page.page, page.per_page)


@router.post("/{post_id}/review", response_model=Message)
async def review_post(
    post_id: int,
    payload: PostModerationDecision,
    db: DbSession,
    user: Annotated[User, require(Perm.POST_MODERATE)],
) -> Message:
    post = await db.scalar(service.base_query().where(Post.id == post_id))
    if post is None:
        raise NotFound("No post with that id.")
    if post.status != PostStatus.SUBMITTED:
        raise ValidationFailed("That post is not waiting for review.")

    if payload.approve:
        target = PostStatus.PUBLISHED if payload.publish else PostStatus.DRAFT
        await service.apply_status(db, post, target, actor=user)
        message = "Published." if payload.publish else "Approved and returned to drafts."
    else:
        await service.apply_status(
            db, post, PostStatus.REJECTED, actor=user, reason=payload.reason
        )
        message = "Rejected. The author has been told why."

    # Guest authors have no account, so they are told by e-mail directly.
    if post.author_id is None and post.guest_email and payload.notify_author:
        from app.services.email import send_email

        await send_email(
            db,
            to_address=post.guest_email,
            template="post_approved" if payload.approve else "post_rejected",
            context={
                "name": post.guest_name or "there",
                "title": post.title,
                "reason": payload.reason or "No reason was given.",
                "action_url": f"{__import__('app.core.config', fromlist=['settings']).settings.SITE_URL}/blog/{post.slug}",
            },
        )

    await db.commit()
    return Message(detail=message)


@router.post("/{post_id}/feature", response_model=Message)
async def toggle_feature(
    post_id: int,
    db: DbSession,
    _: Annotated[User, require(Perm.POST_FEATURE)],
    featured: bool = True,
) -> Message:
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFound("No post with that id.")
    post.is_featured = featured
    await db.commit()
    return Message(detail="Featured." if featured else "Removed from featured.")


# --------------------------------------------------------- reader interaction
@router.post("/{post_id}/reactions", response_model=ReactionSummary)
async def react(
    post_id: int,
    payload: PostReactionIn,
    db: DbSession,
    user: MaybeUser,
    anon: AnonKey,
) -> ReactionSummary:
    """Add, switch or remove a reaction. Re-sending the same one removes it."""
    post = await db.get(Post, post_id)
    if post is None or not post.allow_reactions:
        raise NotFound("Reactions are off for this post.")

    condition = (
        PostReaction.user_id == user.id if user else PostReaction.anon_key == anon
    )
    existing = await db.scalar(
        select(PostReaction).where(PostReaction.post_id == post_id, condition)
    )

    if existing is None:
        db.add(
            PostReaction(
                post_id=post_id,
                user_id=user.id if user else None,
                anon_key=None if user else anon,
                type=payload.type,
            )
        )
        post.reaction_count += 1
        mine = payload.type
        if post.author_id and user:
            await notifications.notify(
                db,
                recipient=post.author_id,
                kind=NotificationKind.REACTION,
                title=f"{user.display_name} reacted to “{post.title}”",
                url=f"/blog/{post.slug}",
                actor=user,
                subject_type="post",
                subject_id=post.id,
                group_key=f"reactions:{post.id}",
            )
    elif existing.type == payload.type:
        await db.delete(existing)
        post.reaction_count = max(0, post.reaction_count - 1)
        mine = None
    else:
        existing.type = payload.type
        mine = payload.type

    await db.commit()

    rows = await db.execute(
        select(PostReaction.type, func.count(PostReaction.id))
        .where(PostReaction.post_id == post_id)
        .group_by(PostReaction.type)
    )
    counts = {kind: count for kind, count in rows.all()}
    return ReactionSummary(counts=counts, total=sum(counts.values()), my_reaction=mine)


@router.post("/{post_id}/view", response_model=Message, status_code=202)
async def record_view(
    post_id: int,
    payload: PostViewIn,
    request: Request,
    db: DbSession,
    user: MaybeUser,
    anon: AnonKey,
) -> Message:
    """Log a read. Counted once per reader per day."""
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFound("No post with that id.")

    today = datetime.now(timezone.utc).date()
    already = await db.scalar(
        select(PostView.id).where(
            PostView.post_id == post_id,
            PostView.anon_key == anon,
            func.date(PostView.created_at) == today,
        )
    )
    db.add(
        PostView(
            post_id=post_id,
            user_id=user.id if user else None,
            anon_key=anon,
            referrer=payload.referrer,
            seconds_on_page=payload.seconds_on_page,
            scroll_depth=payload.scroll_depth,
        )
    )
    post.view_count += 1
    if already is None:
        post.unique_view_count += 1
    await db.commit()
    return Message(detail="Recorded.", code="recorded")


@router.post("/{post_id}/bookmark", response_model=Message)
async def toggle_bookmark(post_id: int, db: DbSession, user: CurrentUser) -> Message:
    existing = await db.scalar(
        select(Bookmark).where(Bookmark.post_id == post_id, Bookmark.user_id == user.id)
    )
    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return Message(detail="Bookmark removed.", code="removed")
    db.add(Bookmark(post_id=post_id, user_id=user.id))
    await db.commit()
    return Message(detail="Saved to your bookmarks.", code="added")
