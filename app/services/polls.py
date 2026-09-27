"""Poll voting and result shaping."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.models.poll import Poll, PollOption, PollVote
from app.models.user import User
from app.schemas.post import PollOptionRead, PollRead


def _vote_filter(poll_id: int, user: User | None, anon: str):
    if user is not None:
        return (PollVote.poll_id == poll_id) & (PollVote.user_id == user.id)
    return (PollVote.poll_id == poll_id) & (PollVote.anon_key == anon)


async def my_option_ids(
    db: AsyncSession, poll: Poll, user: User | None, anon: str
) -> list[int]:
    rows = await db.scalars(
        select(PollVote.option_id).where(_vote_filter(poll.id, user, anon))
    )
    return list(rows.all())


def is_closed(poll: Poll) -> bool:
    now = datetime.now(timezone.utc)
    if not poll.is_open:
        return True
    return bool(poll.closes_at and poll.closes_at <= now)


def is_open_for_votes(poll: Poll) -> bool:
    now = datetime.now(timezone.utc)
    if is_closed(poll):
        return False
    return not (poll.opens_at and poll.opens_at > now)


async def decorate_poll(
    db: AsyncSession, poll: Poll, user: User | None, anon: str
) -> PollRead:
    """Build the read shape, honouring the result-hiding rules."""
    mine = await my_option_ids(db, poll, user, anon)

    visible = True
    if poll.hide_results_until_closed and not is_closed(poll):
        visible = False
    elif poll.hide_results_until_voted and not mine:
        visible = False

    total = sum(option.vote_count for option in poll.options) or 0
    options = []
    for option in poll.options:
        read = PollOptionRead.model_validate(option)
        read.percentage = round(option.vote_count / total * 100, 1) if total else 0.0
        if not visible:
            # Zero the tally rather than omitting it, so the UI shape is stable.
            read.vote_count = 0
            read.percentage = 0.0
        options.append(read)

    result = PollRead.model_validate(poll)
    result.options = options
    result.my_votes = mine
    result.results_visible = visible
    result.total_votes = total if visible else 0
    result.total_voters = poll.total_voters if visible else 0
    return result


async def cast_vote(
    db: AsyncSession,
    poll: Poll,
    option_ids: list[int],
    *,
    user: User | None,
    anon: str,
    ranks: dict[int, int] | None = None,
    write_in: str | None = None,
) -> Poll:
    if not is_open_for_votes(poll):
        raise Conflict("This poll is closed.")
    if user is None and not poll.allow_anonymous:
        raise Conflict("Sign in to vote in this poll.")

    if write_in:
        if not poll.allow_write_in:
            raise ValidationFailed("This poll does not take write-in answers.")
        option = PollOption(
            poll_id=poll.id,
            label=write_in.strip()[:300],
            position=len(poll.options),
            is_write_in=True,
        )
        db.add(option)
        await db.flush()
        option_ids = [*option_ids, option.id]

    valid_ids = {option.id for option in poll.options} | set(option_ids)
    chosen = [oid for oid in dict.fromkeys(option_ids) if oid in valid_ids]
    if not chosen:
        raise ValidationFailed("Pick at least one option.")

    allowed = poll.max_selections if poll.allow_multiple else 1
    if len(chosen) > allowed:
        raise ValidationFailed(
            f"Choose at most {allowed} option{'s' if allowed > 1 else ''}."
        )

    previous = await my_option_ids(db, poll, user, anon)
    if previous and not poll.allow_vote_change:
        raise Conflict("You have already voted, and this poll does not allow changes.")

    if previous:
        await db.execute(delete(PollVote).where(_vote_filter(poll.id, user, anon)))

    for option_id in chosen:
        db.add(
            PollVote(
                poll_id=poll.id,
                option_id=option_id,
                user_id=user.id if user else None,
                anon_key=None if user else anon,
                rank=(ranks or {}).get(option_id),
            )
        )
    await db.flush()
    await recount(db, poll)
    return poll


async def clear_vote(
    db: AsyncSession, poll: Poll, *, user: User | None, anon: str
) -> Poll:
    if not poll.allow_vote_change:
        raise Conflict("This poll does not allow changes.")
    await db.execute(delete(PollVote).where(_vote_filter(poll.id, user, anon)))
    await db.flush()
    await recount(db, poll)
    return poll


async def recount(db: AsyncSession, poll: Poll) -> None:
    """Recompute every counter from the vote rows — the single source of truth."""
    rows = await db.execute(
        select(PollVote.option_id, func.count(PollVote.id))
        .where(PollVote.poll_id == poll.id)
        .group_by(PollVote.option_id)
    )
    tallies = dict(rows.all())
    for option in poll.options:
        option.vote_count = tallies.get(option.id, 0)

    poll.total_votes = sum(tallies.values())
    poll.total_voters = (
        await db.scalar(
            select(
                func.count(
                    func.distinct(func.coalesce(PollVote.user_id, PollVote.anon_key))
                )
            ).where(PollVote.poll_id == poll.id)
        )
    ) or 0
    await db.flush()


async def get_or_404(db: AsyncSession, poll_id: int) -> Poll:
    poll = await db.get(Poll, poll_id)
    if poll is None:
        raise NotFound("No poll with that id.")
    return poll
