"""Poll voting."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AnonKey, CurrentUser, DbSession, MaybeUser, require
from app.core.exceptions import NotFound
from app.core.permissions import Perm
from app.models.poll import Poll, PollOption, PollVote
from app.models.post import Post
from app.models.user import User
from app.schemas.common import Message
from app.schemas.post import PollIn, PollRead, PollVoteIn, PollVoterRead
from app.services import polls as service
from app.services.posts import upsert_poll

router = APIRouter(prefix="/polls", tags=["polls"])


@router.get("/{poll_id}", response_model=PollRead)
async def read_poll(
    poll_id: int, db: DbSession, user: MaybeUser, anon: AnonKey
) -> PollRead:
    poll = await service.get_or_404(db, poll_id)
    return await service.decorate_poll(db, poll, user, anon)


@router.post("/{poll_id}/vote", response_model=PollRead)
async def vote(
    poll_id: int,
    payload: PollVoteIn,
    db: DbSession,
    user: MaybeUser,
    anon: AnonKey,
) -> PollRead:
    poll = await service.get_or_404(db, poll_id)
    await service.cast_vote(
        db,
        poll,
        payload.option_ids,
        user=user,
        anon=anon,
        ranks=payload.ranks,
        write_in=payload.write_in,
    )
    await db.commit()
    await db.refresh(poll)
    return await service.decorate_poll(db, poll, user, anon)


@router.delete("/{poll_id}/vote", response_model=PollRead)
async def retract(
    poll_id: int, db: DbSession, user: MaybeUser, anon: AnonKey
) -> PollRead:
    poll = await service.get_or_404(db, poll_id)
    await service.clear_vote(db, poll, user=user, anon=anon)
    await db.commit()
    return await service.decorate_poll(db, poll, user, anon)


@router.post("/post/{post_id}", response_model=PollRead)
async def attach_poll(
    post_id: int,
    payload: PollIn,
    db: DbSession,
    anon: AnonKey,
    user: Annotated[User, require(Perm.POST_CREATE)],
) -> PollRead:
    """Create a standalone poll on a post, outside the block editor."""
    post = await db.get(Post, post_id)
    if post is None:
        raise NotFound("No post with that id.")
    poll = await upsert_poll(db, post, payload)
    await db.commit()
    await db.refresh(poll)
    return await service.decorate_poll(db, poll, user, anon)


@router.post("/{poll_id}/close", response_model=Message)
async def close_poll(
    poll_id: int,
    db: DbSession,
    _: Annotated[User, require(Perm.POST_EDIT_ANY, Perm.POST_MODERATE)],
    open_again: bool = False,
) -> Message:
    poll = await service.get_or_404(db, poll_id)
    poll.is_open = open_again
    await db.commit()
    return Message(detail="Poll reopened." if open_again else "Poll closed.")


@router.get("/{poll_id}/voters", response_model=list[PollVoterRead])
async def poll_voters(poll_id: int, db: DbSession, user: CurrentUser) -> list[PollVoterRead]:
    """Who voted and for what — visible to the post's author and moderators only."""
    poll = await service.get_or_404(db, poll_id)
    post = await db.get(Post, poll.post_id)
    allowed = user.has_permission(Perm.POST_MODERATE) or (
        post is not None and post.author_id == user.id
    )
    if not allowed:
        raise NotFound("No poll with that id.")

    rows = (
        await db.execute(
            select(PollVote, PollOption.label, User)
            .join(PollOption, PollVote.option_id == PollOption.id)
            .outerjoin(User, PollVote.user_id == User.id)
            .where(PollVote.poll_id == poll_id)
            .order_by(PollVote.created_at.desc())
        )
    ).all()

    return [
        PollVoterRead(
            option_id=vote.option_id,
            option_label=label,
            voter_name=voter.display_name if voter else "Anonymous reader",
            is_registered=voter is not None,
            voted_at=vote.created_at,
        )
        for vote, label, voter in rows
    ]
