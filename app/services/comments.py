"""Comment creation, threading, moderation and spam heuristics."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import settings
from app.core.permissions import Perm
from app.models.comment import Comment
from app.models.enums import ModerationState, NotificationKind
from app.models.post import Post
from app.models.user import User
from app.services import notifications, settings_store
from app.services.text import (
    build_excerpt,
    extract_mentions,
    linkify_mentions,
    render_markdown,
)

_URL_RE = re.compile(r"https?://", re.IGNORECASE)


def anon_key(ip: str | None, user_agent: str | None) -> str:
    """A stable, non-reversible identifier for a signed-out reader."""
    raw = f"{ip or ''}|{user_agent or ''}|{settings.SECRET_KEY}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def spam_score(body: str, *, is_guest: bool, website: str | None) -> int:
    """Cheap heuristics, 0–100. High scores go to the moderation queue."""
    score = 0
    links = len(_URL_RE.findall(body))
    score += min(40, links * 12)
    if len(body) < 15:
        score += 10
    letters = [c for c in body if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        score += 15
    if is_guest:
        score += 10
    if website:
        score += 5
    for term in ("casino", "viagra", "crypto giveaway", "seo services", "buy followers"):
        if term in body.lower():
            score += 30
    return min(100, score)


async def initial_state(
    db: AsyncSession, *, score: int, is_guest: bool, author: User | None
) -> str:
    if author is not None and author.has_permission(Perm.COMMENT_MODERATE):
        return ModerationState.APPROVED
    if score >= 60:
        return ModerationState.SPAM
    if score >= 35:
        return ModerationState.PENDING
    auto = await settings_store.get_setting(db, "auto_approve_comments", True)
    if auto:
        return ModerationState.APPROVED
    return ModerationState.PENDING


async def create_comment(
    db: AsyncSession,
    *,
    post: Post,
    body: str,
    author: User | None,
    parent: Comment | None = None,
    guest_name: str | None = None,
    guest_email: str | None = None,
    guest_website: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Comment:
    is_guest = author is None
    score = spam_score(body, is_guest=is_guest, website=guest_website)
    state = await initial_state(db, score=score, is_guest=is_guest, author=author)

    html = linkify_mentions(render_markdown(body))
    comment = Comment(
        post_id=post.id,
        parent_id=parent.id if parent else None,
        depth=(parent.depth + 1) if parent else 0,
        author_id=author.id if author else None,
        guest_name=guest_name,
        guest_email=guest_email,
        guest_website=guest_website,
        body=body,
        body_html=html,
        mentions=extract_mentions(body),
        moderation_state=state,
        spam_score=score,
        is_author_reply=bool(author and author.id == post.author_id),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(comment)
    await db.flush()

    comment.path = f"{parent.path}.{comment.id}" if parent else str(comment.id)
    if parent is not None:
        parent.reply_count += 1
    if state == ModerationState.APPROVED:
        post.comment_count += 1
    await db.flush()

    if state == ModerationState.APPROVED:
        await fan_out(db, post=post, comment=comment, parent=parent, actor=author)
    elif state == ModerationState.PENDING:
        await notifications.notify_permission_holders(
            db,
            Perm.COMMENT_MODERATE,
            kind=NotificationKind.COMMENT_FLAGGED,
            title="A comment is waiting for review",
            body=build_excerpt(body, 140),
            url=f"/dashboard/comments?state=pending",
            subject_type="comment",
            subject_id=comment.id,
        )
    return comment


async def fan_out(
    db: AsyncSession,
    *,
    post: Post,
    comment: Comment,
    parent: Comment | None,
    actor: User | None,
) -> None:
    """Notify the thread parent, the post author and anyone mentioned."""
    excerpt = build_excerpt(comment.body, 160)
    url = f"/blog/{post.slug}#comment-{comment.id}"
    notified: set[int] = set()

    if parent is not None and parent.author_id:
        await notifications.notify(
            db,
            recipient=parent.author_id,
            kind=NotificationKind.REPLY_TO_COMMENT,
            title=f"{comment.display_name} replied to you",
            body=excerpt,
            url=url,
            actor=actor,
            subject_type="comment",
            subject_id=comment.id,
            email_template="comment_reply",
            email_context={
                "actor": comment.display_name,
                "title": post.title,
                "excerpt": excerpt,
            },
        )
        notified.add(parent.author_id)

    if post.author_id and post.author_id not in notified:
        await notifications.notify(
            db,
            recipient=post.author_id,
            kind=NotificationKind.COMMENT_ON_POST,
            title=f"New comment on “{post.title}”",
            body=excerpt,
            url=url,
            actor=actor,
            subject_type="comment",
            subject_id=comment.id,
            group_key=f"comments:{post.id}",
        )
        notified.add(post.author_id)

    if comment.mentions:
        mentioned = (
            await db.scalars(select(User).where(User.username.in_(comment.mentions)))
        ).all()
        for user in mentioned:
            if user.id in notified:
                continue
            await notifications.notify(
                db,
                recipient=user,
                kind=NotificationKind.MENTION,
                title=f"{comment.display_name} mentioned you",
                body=excerpt,
                url=url,
                actor=actor,
                subject_type="comment",
                subject_id=comment.id,
                email_template="comment_reply",
                email_context={
                    "actor": comment.display_name,
                    "title": post.title,
                    "excerpt": excerpt,
                },
            )
            notified.add(user.id)


async def moderate(
    db: AsyncSession,
    comment: Comment,
    state: ModerationState,
    *,
    actor: User,
    note: str | None = None,
    cascade: bool = False,
) -> int:
    """Apply a decision, optionally to the whole subtree. Returns rows changed."""
    previous = comment.moderation_state
    targets = [comment]

    if cascade:
        descendants = (
            await db.scalars(
                select(Comment).where(
                    Comment.post_id == comment.post_id,
                    Comment.path.like(f"{comment.path}.%"),
                )
            )
        ).all()
        targets.extend(descendants)

    now = datetime.now(timezone.utc)
    delta = 0
    for target in targets:
        was_visible = target.moderation_state == ModerationState.APPROVED
        target.moderation_state = state
        target.moderated_by_id = actor.id
        target.moderated_at = now
        target.moderation_note = note
        now_visible = state == ModerationState.APPROVED
        if was_visible and not now_visible:
            delta -= 1
        elif now_visible and not was_visible:
            delta += 1

    if delta:
        post = await db.get(Post, comment.post_id)
        if post is not None:
            post.comment_count = max(0, post.comment_count + delta)

    await db.flush()

    if previous != ModerationState.APPROVED and state == ModerationState.APPROVED:
        post = await db.get(Post, comment.post_id)
        parent = await db.get(Comment, comment.parent_id) if comment.parent_id else None
        if post is not None:
            await fan_out(db, post=post, comment=comment, parent=parent, actor=None)

    return len(targets)


def visible_filter(user: User | None):
    if user is not None and user.has_permission(Perm.COMMENT_MODERATE):
        return Comment.deleted_at.is_(None)
    approved = (Comment.moderation_state == ModerationState.APPROVED) & Comment.deleted_at.is_(None)
    if user is None:
        return approved
    # Authors always see their own comment, even while it is held for review.
    return approved | ((Comment.author_id == user.id) & Comment.deleted_at.is_(None))


def thread_query(post_id: int, user: User | None):
    return (
        select(Comment)
        .where(Comment.post_id == post_id, visible_filter(user))
        .options(selectinload(Comment.author))
        .order_by(Comment.is_pinned.desc(), Comment.path)
    )


def nest(rows: list[Comment]) -> list[Comment]:
    """Turn a path-ordered flat list into a tree, in one pass."""
    by_id: dict[int, Comment] = {}
    roots: list[Comment] = []
    for row in rows:
        # Marks the collection loaded without emitting a lazy load.
        set_committed_value(row, "replies", [])
        by_id[row.id] = row
    for row in rows:
        parent = by_id.get(row.parent_id) if row.parent_id else None
        if parent is not None:
            parent.replies.append(row)
        else:
            roots.append(row)
    return roots


async def count_for_post(db: AsyncSession, post_id: int) -> int:
    return (
        await db.scalar(
            select(func.count(Comment.id)).where(
                Comment.post_id == post_id,
                Comment.moderation_state == ModerationState.APPROVED,
                Comment.deleted_at.is_(None),
            )
        )
    ) or 0
