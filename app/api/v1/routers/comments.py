"""Comments, replies, reactions, reports and the moderation queue."""

from __future__ import annotations

from typing import Annotated

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
from app.core.exceptions import (
    Conflict,
    NotFound,
    PermissionDenied,
    ValidationFailed,
)
from app.core.permissions import Perm
from app.models.comment import Comment, CommentReaction, CommentReport
from app.models.enums import ModerationState, NotificationKind
from app.models.post import Post
from app.models.user import User
from app.schemas.comment import (
    CommentCreate,
    CommentModerationIn,
    CommentPin,
    CommentReactionIn,
    CommentRead,
    CommentReportIn,
    CommentUpdate,
)
from app.schemas.common import Message, Page
from sqlalchemy.orm.attributes import set_committed_value

from app.services import comments as service, notifications, settings_store
from app.services.text import linkify_mentions, render_markdown

router = APIRouter(tags=["comments"])


def _decorate(row: Comment, user: User | None) -> CommentRead:
    read = CommentRead.model_validate(row)
    read.display_name = row.display_name
    owns = bool(user and user.id == row.author_id)
    read.can_edit = owns and bool(user and user.has_permission(Perm.COMMENT_EDIT_OWN))
    read.can_delete = owns or bool(user and user.has_permission(Perm.COMMENT_MODERATE))
    read.can_moderate = bool(user and user.has_permission(Perm.COMMENT_MODERATE))
    read.replies = [_decorate(reply, user) for reply in getattr(row, "replies", [])]
    return read


@router.get("/posts/{post_id}/comments", response_model=list[CommentRead])
async def list_comments(
    post_id: int,
    db: DbSession,
    user: MaybeUser,
    anon: AnonKey,
    flat: Annotated[bool, Query()] = False,
) -> list[CommentRead]:
    """The whole thread. Returned nested by default, flat when asked."""
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFound("No post with that id.")

    rows = list((await db.scalars(service.thread_query(post_id, user))).unique().all())

    reacted: dict[int, str] = {}
    if rows:
        ids = [row.id for row in rows]
        condition = (
            CommentReaction.user_id == user.id
            if user
            else CommentReaction.anon_key == anon
        )
        mine = await db.execute(
            select(CommentReaction.comment_id, CommentReaction.type).where(
                CommentReaction.comment_id.in_(ids), condition
            )
        )
        reacted = dict(mine.all())

    if flat:
        out = []
        for row in rows:
            set_committed_value(row, "replies", [])
            read = _decorate(row, user)
            read.my_reaction = reacted.get(row.id)
            out.append(read)
        return out

    tree = service.nest(rows)
    result = [_decorate(root, user) for root in tree]

    def apply_reactions(items: list[CommentRead]) -> None:
        for item in items:
            item.my_reaction = reacted.get(item.id)
            apply_reactions(item.replies)

    apply_reactions(result)
    return result


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    post_id: int,
    payload: CommentCreate,
    request: Request,
    db: DbSession,
    user: MaybeUser,
) -> CommentRead:
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFound("No post with that id.")
    if not post.allow_comments:
        raise Conflict("Comments are closed on this post.")

    # Honeypot: only a bot fills a field that is hidden from browsers.
    if payload.website_url:
        return _decorate(
            Comment(
                id=0, post_id=post_id, body=payload.body, body_html="",
                path="0", depth=0, moderation_state=ModerationState.SPAM,
            ),
            user,
        )

    if user is None:
        if await settings_store.get_setting(db, "comments_require_login", False):
            raise PermissionDenied("Sign in to join the conversation.")
        if not payload.guest_name or not payload.guest_email:
            raise ValidationFailed("Add your name and e-mail to comment as a guest.")
    elif not user.has_permission(Perm.COMMENT_CREATE):
        raise PermissionDenied("Your account cannot comment.")

    parent = None
    if payload.parent_id:
        parent = await db.get(Comment, payload.parent_id)
        if parent is None or parent.post_id != post_id:
            raise NotFound("The comment you are replying to is gone.")
        if parent.depth >= 6:
            # Keep threads readable; deeper replies attach to the same level.
            parent = await db.get(Comment, parent.parent_id) or parent

    comment = await service.create_comment(
        db,
        post=post,
        body=payload.body,
        author=user,
        parent=parent,
        guest_name=payload.guest_name,
        guest_email=str(payload.guest_email) if payload.guest_email else None,
        guest_website=payload.guest_website,
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    await db.commit()
    # A full refresh: server-side defaults (timestamps) are not loaded by the
    # INSERT, and the reply collection has to be present before serialising.
    await db.refresh(comment, ["author", "created_at", "updated_at"])
    set_committed_value(comment, "replies", [])

    read = _decorate(comment, user)
    if comment.moderation_state != ModerationState.APPROVED:
        read.body_html += (
            '<p class="text-muted text-sm mt-2">'
            "Held for review — it appears once approved.</p>"
        )
    return read


@router.patch("/comments/{comment_id}", response_model=CommentRead)
async def edit_comment(
    comment_id: int, payload: CommentUpdate, db: DbSession, user: CurrentUser
) -> CommentRead:
    comment = await db.scalar(
        select(Comment).where(Comment.id == comment_id).options(selectinload(Comment.author))
    )
    if comment is None or comment.deleted_at is not None:
        raise NotFound("No comment with that id.")

    owns = comment.author_id == user.id
    if not (owns and user.has_permission(Perm.COMMENT_EDIT_OWN)) and not user.has_permission(
        Perm.COMMENT_MODERATE
    ):
        raise PermissionDenied("You can only edit your own comments.")

    comment.body = payload.body
    comment.body_html = linkify_mentions(render_markdown(payload.body))
    comment.is_edited = True
    await db.commit()
    await db.refresh(comment, ["updated_at"])
    set_committed_value(comment, "replies", [])
    return _decorate(comment, user)


@router.delete("/comments/{comment_id}", response_model=Message)
async def delete_comment(
    comment_id: int, db: DbSession, user: CurrentUser
) -> Message:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise NotFound("No comment with that id.")

    owns = comment.author_id == user.id
    if not (owns and user.has_permission(Perm.COMMENT_DELETE_OWN)) and not user.has_permission(
        Perm.COMMENT_MODERATE
    ):
        raise PermissionDenied("You can only delete your own comments.")

    was_visible = comment.moderation_state == ModerationState.APPROVED
    comment.soft_delete()
    if was_visible:
        post = await db.get(Post, comment.post_id)
        if post is not None:
            post.comment_count = max(0, post.comment_count - 1)
    await db.commit()
    return Message(detail="Comment removed.")


@router.post("/comments/{comment_id}/reactions", response_model=Message)
async def react_to_comment(
    comment_id: int,
    payload: CommentReactionIn,
    db: DbSession,
    user: MaybeUser,
    anon: AnonKey,
) -> Message:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise NotFound("No comment with that id.")

    condition = (
        CommentReaction.user_id == user.id if user else CommentReaction.anon_key == anon
    )
    existing = await db.scalar(
        select(CommentReaction).where(
            CommentReaction.comment_id == comment_id, condition
        )
    )
    if existing is None:
        db.add(
            CommentReaction(
                comment_id=comment_id,
                user_id=user.id if user else None,
                anon_key=None if user else anon,
                type=payload.type,
            )
        )
        comment.reaction_count += 1
        detail, code = "Reaction added.", "added"
    elif existing.type == payload.type:
        await db.delete(existing)
        comment.reaction_count = max(0, comment.reaction_count - 1)
        detail, code = "Reaction removed.", "removed"
    else:
        existing.type = payload.type
        detail, code = "Reaction changed.", "changed"

    await db.commit()
    return Message(detail=detail, code=code)


@router.post("/comments/{comment_id}/report", response_model=Message)
async def report_comment(
    comment_id: int, payload: CommentReportIn, db: DbSession, user: MaybeUser
) -> Message:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise NotFound("No comment with that id.")

    db.add(
        CommentReport(
            comment_id=comment_id,
            reporter_id=user.id if user else None,
            reason=payload.reason,
            detail=payload.detail,
        )
    )
    comment.report_count += 1

    threshold = await settings_store.get_setting(db, "comment_report_threshold", 3)
    if comment.report_count >= int(threshold) and comment.moderation_state == ModerationState.APPROVED:
        comment.moderation_state = ModerationState.HIDDEN
        post = await db.get(Post, comment.post_id)
        if post is not None:
            post.comment_count = max(0, post.comment_count - 1)
        await notifications.notify_permission_holders(
            db,
            Perm.COMMENT_MODERATE,
            kind=NotificationKind.COMMENT_FLAGGED,
            title="A comment was hidden after several reports",
            url="/dashboard/comments?state=hidden",
            subject_type="comment",
            subject_id=comment.id,
        )

    await db.commit()
    return Message(detail="Thanks — a moderator will look at it.")


# --------------------------------------------------------------- moderation
@router.get("/comments/queue", response_model=Page[CommentRead])
async def moderation_queue(
    db: DbSession,
    page: Pagination,
    user: Annotated[User, require(Perm.COMMENT_MODERATE)],
    state: str = ModerationState.PENDING,
) -> Page[CommentRead]:
    stmt = (
        select(Comment)
        .where(Comment.moderation_state == state, Comment.deleted_at.is_(None))
        .options(selectinload(Comment.author))
    )
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(Comment.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
    ).unique().all()
    items = []
    for row in rows:
        set_committed_value(row, "replies", [])
        items.append(_decorate(row, user))
    return Page.build(items, total or 0, page.page, page.per_page)


@router.post("/comments/{comment_id}/moderate", response_model=Message)
async def moderate_comment(
    comment_id: int,
    payload: CommentModerationIn,
    db: DbSession,
    user: Annotated[User, require(Perm.COMMENT_MODERATE)],
) -> Message:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise NotFound("No comment with that id.")

    changed = await service.moderate(
        db, comment, payload.state, actor=user, note=payload.note, cascade=payload.cascade
    )
    await db.commit()
    suffix = f" ({changed} comments)" if changed > 1 else ""
    return Message(detail=f"Marked as {payload.state}{suffix}.")


@router.post("/comments/{comment_id}/pin", response_model=Message)
async def pin_comment(
    comment_id: int,
    payload: CommentPin,
    db: DbSession,
    _: Annotated[User, require(Perm.COMMENT_MODERATE)],
) -> Message:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise NotFound("No comment with that id.")
    comment.is_pinned = payload.pinned
    await db.commit()
    return Message(detail="Pinned to the top." if payload.pinned else "Unpinned.")
