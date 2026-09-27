"""Post lifecycle: writing, block sync, revisions, review and publishing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.core.permissions import Perm
from app.models.enums import BlockType, NotificationKind, PostStatus, PostVisibility
from app.models.poll import Poll, PollOption
from app.models.post import ContentBlock, Post, PostRevision
from app.models.taxonomy import Tag
from app.models.user import User
from app.schemas.post import ContentBlockIn, PollIn
from app.services import notifications, settings_store
from app.services.text import (
    build_excerpt,
    highlight_code,
    render_markdown,
    sanitize_post_html,
    slugify,
    to_plain_text,
    word_count,
)


# ------------------------------------------------------------------- slugs
async def unique_slug(db: AsyncSession, title: str, *, post_id: int | None = None) -> str:
    base = slugify(title)
    candidate, suffix = base, 2
    while True:
        stmt = select(Post.id).where(Post.slug == candidate)
        if post_id:
            stmt = stmt.where(Post.id != post_id)
        if await db.scalar(stmt) is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


async def ensure_loaded(db: AsyncSession, instance, *names: str) -> None:
    """Load relationship collections before use.

    Touching an unloaded collection on a flushed object raises
    ``MissingGreenlet`` under the async engine, because the implicit lazy load
    would be blocking IO. Refreshing first keeps callers from having to think
    about it.
    """
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy.orm.attributes import set_committed_value

    state = sa_inspect(instance)
    pending = [name for name in names if name in state.unloaded]
    if pending and state.persistent:
        await db.refresh(instance, pending)
    for name in names:
        # A brand-new object has no persistent row to refresh from, so mark
        # the collection loaded and empty rather than leaving it to lazy-load.
        if name in sa_inspect(instance).unloaded:
            set_committed_value(instance, name, [])


# -------------------------------------------------------------------- tags
async def sync_tags(db: AsyncSession, post: Post, names: Iterable[str]) -> None:
    await ensure_loaded(db, post, "tags")
    wanted = {slugify(n): n.strip() for n in names if n and n.strip()}
    for tag in list(post.tags):
        if tag.slug not in wanted:
            tag.usage_count = max(0, tag.usage_count - 1)
            post.tags.remove(tag)

    existing = {tag.slug for tag in post.tags}
    for slug, name in wanted.items():
        if slug in existing:
            continue
        tag = await db.scalar(select(Tag).where(Tag.slug == slug))
        if tag is None:
            tag = Tag(name=name[:60], slug=slug)
            db.add(tag)
            await db.flush()
        tag.usage_count += 1
        post.tags.append(tag)


# ------------------------------------------------------------------ blocks
def _rendered_text(block: ContentBlock) -> str:
    """Plain text of one block, for word count and excerpt generation."""
    data = block.data or {}
    if block.type in {BlockType.RICH_TEXT, BlockType.CALLOUT, BlockType.HTML}:
        return to_plain_text(data.get("html", ""))
    if block.type == BlockType.MARKDOWN:
        return to_plain_text(data.get("source", ""))
    if block.type in {BlockType.HEADING, BlockType.QUOTE}:
        return data.get("text", "")
    if block.type == BlockType.LIST:
        return " ".join(str(i) for i in data.get("items", []))
    if block.type == BlockType.CODE:
        return ""  # code should not inflate the reading estimate
    return data.get("caption") or ""


def normalise_block(payload: ContentBlockIn) -> dict[str, Any]:
    """Sanitise and pre-render a block payload before it is stored.

    Rendering at write time means the read path is a straight select — no
    markdown or Pygments work on every page view.
    """
    data = dict(payload.data)

    if payload.type in {BlockType.RICH_TEXT, BlockType.CALLOUT, BlockType.HTML}:
        data["html"] = sanitize_post_html(data.get("html", ""))
    elif payload.type == BlockType.MARKDOWN:
        data["html"] = render_markdown(data.get("source", ""), trusted=True)
    elif payload.type == BlockType.CODE:
        data["html"] = highlight_code(
            data.get("source", ""),
            data.get("language", "text"),
            filename=data.get("filename"),
            line_numbers=bool(data.get("show_line_numbers", True)),
            highlight_lines=data.get("highlight_lines") or [],
        )
    elif payload.type == BlockType.EMBED:
        data["embed_url"] = data.get("embed_url", "").strip()

    return data


async def sync_blocks(
    db: AsyncSession, post: Post, blocks: list[ContentBlockIn]
) -> None:
    """Replace the post body with ``blocks``, reusing rows where ids match."""
    await ensure_loaded(db, post, "blocks")
    by_id = {block.id: block for block in post.blocks}
    keep: set[int] = set()

    for position, payload in enumerate(blocks):
        data = normalise_block(payload)

        if payload.type == BlockType.POLL and payload.poll is not None:
            poll = await upsert_poll(db, post, payload.poll, data.get("poll_id"))
            data["poll_id"] = poll.id

        row = by_id.get(payload.id) if payload.id else None
        if row is None:
            row = ContentBlock(post_id=post.id)
            post.blocks.append(row)
        row.type = payload.type
        row.position = position
        row.data = data
        row.settings = payload.settings
        row.anchor = payload.anchor or (
            slugify(data.get("text", ""))[:120]
            if payload.type == BlockType.HEADING
            else None
        )
        row.is_hidden = payload.is_hidden
        await db.flush()
        keep.add(row.id)

    for row in list(post.blocks):
        if row.id and row.id not in keep:
            post.blocks.remove(row)

    await db.flush()
    recompute_metrics(post)


def recompute_metrics(post: Post) -> None:
    text = " ".join(_rendered_text(block) for block in post.blocks if not block.is_hidden)
    post.word_count = word_count(text)
    post.reading_minutes = max(1, round(post.word_count / 225)) if post.word_count else 1
    if not post.excerpt:
        post.excerpt = build_excerpt(text)


# -------------------------------------------------------------------- polls
async def upsert_poll(
    db: AsyncSession, post: Post, payload: PollIn, poll_id: int | None = None
) -> Poll:
    poll = await db.get(Poll, poll_id) if poll_id else None
    if poll is None:
        poll = Poll(post_id=post.id)
        db.add(poll)

    poll.question = payload.question
    poll.description = payload.description
    poll.type = payload.type
    poll.allow_multiple = payload.allow_multiple
    poll.max_selections = max(1, payload.max_selections)
    poll.allow_anonymous = payload.allow_anonymous
    poll.allow_vote_change = payload.allow_vote_change
    poll.allow_write_in = payload.allow_write_in
    poll.hide_results_until_voted = payload.hide_results_until_voted
    poll.hide_results_until_closed = payload.hide_results_until_closed
    poll.opens_at = payload.opens_at
    poll.closes_at = payload.closes_at
    await db.flush()
    await ensure_loaded(db, poll, "options")

    existing = {option.id: option for option in poll.options}
    keep: set[int] = set()
    for position, option_payload in enumerate(payload.options):
        option = existing.get(option_payload.id) if option_payload.id else None
        if option is None:
            option = PollOption(poll_id=poll.id)
            poll.options.append(option)
        option.label = option_payload.label
        option.description = option_payload.description
        option.image_url = option_payload.image_url
        option.icon = option_payload.icon
        option.accent = option_payload.accent
        option.position = position
        await db.flush()
        keep.add(option.id)

    for option in list(poll.options):
        # Removing an option deletes its votes; the tally is recomputed below.
        if option.id and option.id not in keep:
            poll.options.remove(option)

    await db.flush()
    poll.total_votes = sum(option.vote_count for option in poll.options)
    return poll


# ---------------------------------------------------------------- lifecycle
async def snapshot(
    db: AsyncSession, post: Post, editor: User | None, note: str | None = None
) -> PostRevision:
    number = (
        await db.scalar(
            select(func.count(PostRevision.id)).where(PostRevision.post_id == post.id)
        )
    ) or 0
    revision = PostRevision(
        post_id=post.id,
        editor_id=editor.id if editor else None,
        revision_number=number + 1,
        title=post.title,
        change_note=note,
        snapshot={
            "title": post.title,
            "subtitle": post.subtitle,
            "excerpt": post.excerpt,
            "blocks": [
                {"type": b.type, "position": b.position, "data": b.data, "settings": b.settings}
                for b in post.blocks
            ],
        },
    )
    db.add(revision)
    return revision


async def resolve_target_status(
    db: AsyncSession, requested: PostStatus, author: User | None
) -> PostStatus:
    """Decide what status a save actually lands in.

    Anyone without ``post:publish`` who asks to publish is routed into the
    review queue instead — unless the auto-publish switch is on, in which case
    their submission goes straight live.
    """
    if requested != PostStatus.PUBLISHED:
        return requested
    if author is not None and author.has_permission(Perm.POST_PUBLISH):
        return PostStatus.PUBLISHED
    auto = await settings_store.get_setting(db, "auto_publish_submissions", False)
    return PostStatus.PUBLISHED if auto else PostStatus.SUBMITTED


async def apply_status(
    db: AsyncSession,
    post: Post,
    status: PostStatus,
    *,
    actor: User | None = None,
    reason: str | None = None,
    scheduled_for: datetime | None = None,
) -> Post:
    now = datetime.now(timezone.utc)
    previous = post.status
    post.status = status

    if status == PostStatus.PUBLISHED and post.published_at is None:
        post.published_at = now
    if status == PostStatus.SUBMITTED:
        post.submitted_at = now
    if status == PostStatus.SCHEDULED:
        post.scheduled_for = scheduled_for or post.scheduled_for
    if status in {PostStatus.PUBLISHED, PostStatus.REJECTED}:
        post.reviewed_at = now
        post.reviewed_by_id = actor.id if actor else None
    if status == PostStatus.REJECTED:
        post.rejection_reason = reason

    await db.flush()
    await _notify_status_change(db, post, previous, status, actor)
    return post


async def _notify_status_change(
    db: AsyncSession, post: Post, previous: str, status: str, actor: User | None
) -> None:
    url = f"/blog/{post.slug}"

    if status == PostStatus.SUBMITTED and previous != PostStatus.SUBMITTED:
        await notifications.notify_permission_holders(
            db,
            Perm.POST_MODERATE,
            kind=NotificationKind.POST_SUBMITTED,
            title=f"“{post.title}” is waiting for review",
            body=f"Submitted by {post.byline}.",
            url=f"/dashboard/review/{post.id}",
            actor=actor,
            subject_type="post",
            subject_id=post.id,
            email_template="post_submitted",
            email_context={"author": post.byline, "title": post.title},
        )
        return

    if post.author_id is None:
        return

    if status == PostStatus.PUBLISHED and previous != PostStatus.PUBLISHED:
        await notifications.notify(
            db,
            recipient=post.author_id,
            kind=NotificationKind.POST_APPROVED,
            title=f"“{post.title}” is live",
            url=url,
            actor=actor,
            subject_type="post",
            subject_id=post.id,
            email_template="post_approved",
            email_context={"title": post.title},
        )
    elif status == PostStatus.REJECTED:
        await notifications.notify(
            db,
            recipient=post.author_id,
            kind=NotificationKind.POST_REJECTED,
            title=f"“{post.title}” needs changes",
            body=post.rejection_reason,
            url=f"/dashboard/posts/{post.id}/edit",
            actor=actor,
            subject_type="post",
            subject_id=post.id,
            email_template="post_rejected",
            email_context={
                "title": post.title,
                "reason": post.rejection_reason or "No reason was given.",
            },
        )


# ---------------------------------------------------------------- authority
def can_view(post: Post, user: User | None) -> bool:
    if post.deleted_at is not None:
        return bool(user and user.has_permission(Perm.POST_EDIT_ANY))
    if post.status == PostStatus.PUBLISHED:
        if post.visibility == PostVisibility.MEMBERS:
            return user is not None
        if post.visibility == PostVisibility.PRIVATE:
            return bool(user and (user.id == post.author_id or user.has_permission(Perm.POST_READ_DRAFT)))
        return True
    if user is None:
        return False
    if user.id == post.author_id:
        return True
    return user.has_permission(Perm.POST_READ_DRAFT)


def can_edit(post: Post, user: User | None) -> bool:
    if user is None:
        return False
    if user.has_permission(Perm.POST_EDIT_ANY):
        return True
    return user.id == post.author_id and user.has_permission(Perm.POST_EDIT_OWN)


def can_delete(post: Post, user: User | None) -> bool:
    if user is None:
        return False
    if user.has_permission(Perm.POST_DELETE_ANY):
        return True
    return user.id == post.author_id and user.has_permission(Perm.POST_DELETE_OWN)


def require_edit(post: Post, user: User | None) -> None:
    if not can_edit(post, user):
        raise PermissionDenied("You can only edit your own posts.")


# ------------------------------------------------------------------ queries
def base_query():
    return select(Post).options(
        selectinload(Post.tags),
        selectinload(Post.blocks),
        selectinload(Post.polls).selectinload(Poll.options),
    )


def visible_filter(user: User | None):
    """SQL predicate matching what ``can_view`` allows, for list endpoints."""
    live = (Post.status == PostStatus.PUBLISHED) & (Post.deleted_at.is_(None))
    if user is None:
        return live & (Post.visibility.in_([PostVisibility.PUBLIC]))
    if user.has_permission(Perm.POST_READ_DRAFT):
        return Post.deleted_at.is_(None)
    return (live & Post.visibility.in_([PostVisibility.PUBLIC, PostVisibility.MEMBERS])) | (
        (Post.author_id == user.id) & Post.deleted_at.is_(None)
    )


async def get_by_slug_or_404(db: AsyncSession, slug: str) -> Post:
    post = await db.scalar(base_query().where(Post.slug == slug))
    if post is None:
        raise NotFound("No post with that address.")
    return post


def search_filter(term: str):
    like = f"%{term.strip()}%"
    return or_(Post.title.ilike(like), Post.excerpt.ilike(like), Post.subtitle.ilike(like))
