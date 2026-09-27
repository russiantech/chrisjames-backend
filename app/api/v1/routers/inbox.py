"""Public forms — contact, project brief, newsletter — and the staff inbox."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, or_, select

from app.api.deps import DbSession, MaybeUser, Pagination, client_ip, require
from app.core.config import settings
from app.core.exceptions import NotFound
from app.core.permissions import Perm
from app.models.enums import (
    MessageStatus,
    NotificationKind,
    RequestStatus,
    SubscriberStatus,
)
from app.models.inbox import (
    ContactMessage,
    NewsletterSubscriber,
    ProjectRequest,
)
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.inbox import (
    ContactCreate,
    ContactRead,
    ContactReply,
    ContactUpdate,
    ProjectRequestAck,
    ProjectRequestCreate,
    ProjectRequestRead,
    ProjectRequestUpdate,
    SubscribeIn,
    SubscriberRead,
)
from app.services import notifications
from app.services.email import send_email
from app.services.text import build_excerpt

router = APIRouter(tags=["inbox"])


def _score_lead(payload: ProjectRequestCreate) -> int:
    """Rough triage score so the highest-intent briefs float to the top."""
    score = 20
    if payload.budget_max:
        score += min(30, int(payload.budget_max) // 1000)
    if payload.company:
        score += 10
    if payload.timeline in {"asap", "1_month"}:
        score += 15
    if len(payload.summary) > 400:
        score += 10
    if payload.phone:
        score += 5
    if payload.attachment_ids:
        score += 10
    return min(100, score)


# ------------------------------------------------------------- public forms
@router.post("/contact", response_model=Message, status_code=status.HTTP_201_CREATED)
async def send_contact(
    payload: ContactCreate, request: Request, db: DbSession, user: MaybeUser
) -> Message:
    if payload.website_url:
        # Honeypot tripped. Answer as if it worked so the bot stops retrying.
        return Message(detail="Thanks — your message is on its way.")

    row = ContactMessage(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        company=payload.company,
        subject=payload.subject,
        message=payload.message,
        user_id=user.id if user else None,
        referrer=payload.referrer,
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(row)
    await db.flush()

    excerpt = build_excerpt(payload.message, 300)
    await send_email(
        db,
        to_address=row.email,
        template="contact_ack",
        context={"name": row.name, "excerpt": excerpt},
    )
    await notifications.notify_permission_holders(
        db,
        Perm.INBOX_READ,
        kind=NotificationKind.CONTACT_MESSAGE,
        title=f"New message from {row.name}",
        body=excerpt,
        url=f"/dashboard/inbox/{row.id}",
        subject_type="contact_message",
        subject_id=row.id,
        email_template="contact_admin",
        email_context={
            "name": row.name,
            "email": row.email,
            "subject": row.subject,
            "excerpt": excerpt,
        },
    )
    await db.commit()
    return Message(detail="Thanks — your message landed. I reply within two working days.")


@router.post(
    "/requests", response_model=ProjectRequestAck, status_code=status.HTTP_201_CREATED
)
async def submit_request(
    payload: ProjectRequestCreate, request: Request, db: DbSession, user: MaybeUser
) -> ProjectRequestAck:
    """The "Get started" brief."""
    if payload.website_url:
        return ProjectRequestAck(id=0, reference="skipped", message="Thanks — brief received.")

    row = ProjectRequest(
        **payload.model_dump(exclude={"website_url", "referrer", "utm"}),
        user_id=user.id if user else None,
        referrer=payload.referrer,
        utm=payload.utm,
        ip_address=client_ip(request),
        lead_score=_score_lead(payload),
        status=RequestStatus.NEW,
    )
    row.email = row.email.lower()
    db.add(row)
    await db.flush()

    reference = f"REQ-{row.id:05d}"
    budget = (
        f"{payload.currency} {payload.budget_min or 0:,.0f}–{payload.budget_max or 0:,.0f}"
        if payload.budget_max
        else "not stated"
    )

    await send_email(
        db,
        to_address=row.email,
        template="request_ack",
        context={
            "name": row.name,
            "project_title": row.project_title,
            "reference": reference,
        },
    )
    await notifications.notify_permission_holders(
        db,
        Perm.INBOX_READ,
        kind=NotificationKind.PROJECT_REQUEST,
        title=f"New brief: {row.project_title}",
        body=f"{row.name} · score {row.lead_score}/100",
        url=f"/dashboard/requests/{row.id}",
        subject_type="project_request",
        subject_id=row.id,
        email_template="request_admin",
        email_context={
            "name": row.name,
            "company": row.company or "independent",
            "project_title": row.project_title,
            "budget": budget,
            "timeline": row.timeline or "flexible",
        },
    )
    await db.commit()

    return ProjectRequestAck(
        id=row.id,
        reference=reference,
        message="Brief received. I will come back with questions or a proposal shortly.",
    )


@router.post("/newsletter/subscribe", response_model=Message)
async def subscribe(payload: SubscribeIn, db: DbSession) -> Message:
    if payload.website_url:
        return Message(detail="Check your inbox to confirm.")

    email = payload.email.lower()
    row = await db.scalar(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )
    if row is None:
        row = NewsletterSubscriber(
            email=email,
            name=payload.name,
            topics=payload.topics,
            source=payload.source,
            unsubscribe_token=secrets.token_urlsafe(24),
        )
        db.add(row)
    elif row.status == SubscriberStatus.SUBSCRIBED:
        return Message(detail="You are already on the list.", code="already_subscribed")

    row.status = SubscriberStatus.PENDING
    row.confirm_token = secrets.token_urlsafe(24)
    row.topics = payload.topics or row.topics
    await db.flush()

    await send_email(
        db,
        to_address=email,
        template="newsletter_confirm",
        context={
            "name": row.name or "there",
            "action_url": f"{settings.SITE_URL}/newsletter/confirm?token={row.confirm_token}",
        },
    )
    await db.commit()
    return Message(detail="Almost there — click the link in your inbox to confirm.")


@router.get("/newsletter/confirm", response_model=Message)
async def confirm_subscription(token: str, db: DbSession) -> Message:
    row = await db.scalar(
        select(NewsletterSubscriber).where(NewsletterSubscriber.confirm_token == token)
    )
    if row is None:
        raise NotFound("That confirmation link is not valid.")
    row.status = SubscriberStatus.SUBSCRIBED
    row.confirmed_at = datetime.now(timezone.utc)
    row.confirm_token = None
    await db.commit()
    return Message(detail="You are on the list. Thanks for subscribing.")


@router.get("/newsletter/unsubscribe", response_model=Message)
async def unsubscribe(token: str, db: DbSession) -> Message:
    row = await db.scalar(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.unsubscribe_token == token
        )
    )
    if row is None:
        raise NotFound("That unsubscribe link is not valid.")
    row.status = SubscriberStatus.UNSUBSCRIBED
    row.unsubscribed_at = datetime.now(timezone.utc)
    await db.commit()
    return Message(detail="Unsubscribed. No more e-mail from here.")


# -------------------------------------------------------------- staff inbox
@router.get("/inbox/messages", response_model=Page[ContactRead])
async def list_messages(
    db: DbSession,
    page: Pagination,
    _: Annotated[User, require(Perm.INBOX_READ)],
    message_status: Annotated[str | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[ContactRead]:
    stmt = select(ContactMessage).where(ContactMessage.deleted_at.is_(None))
    if message_status:
        stmt = stmt.where(ContactMessage.status == message_status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ContactMessage.name.ilike(like),
                ContactMessage.email.ilike(like),
                ContactMessage.subject.ilike(like),
                ContactMessage.message.ilike(like),
            )
        )

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(ContactMessage.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
    ).all()
    return Page.build(
        [ContactRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
    )


@router.get("/inbox/messages/{message_id}", response_model=ContactRead)
async def read_message(
    message_id: int, db: DbSession, _: Annotated[User, require(Perm.INBOX_READ)]
) -> ContactMessage:
    row = await db.get(ContactMessage, message_id)
    if row is None:
        raise NotFound("No message with that id.")
    if row.status == MessageStatus.UNREAD:
        row.status = MessageStatus.READ
        await db.commit()
    return row


@router.patch("/inbox/messages/{message_id}", response_model=ContactRead)
async def update_message(
    message_id: int,
    payload: ContactUpdate,
    db: DbSession,
    _: Annotated[User, require(Perm.INBOX_READ)],
) -> ContactMessage:
    row = await db.get(ContactMessage, message_id)
    if row is None:
        raise NotFound("No message with that id.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.post("/inbox/messages/{message_id}/reply", response_model=Message)
async def reply_to_message(
    message_id: int,
    payload: ContactReply,
    db: DbSession,
    user: Annotated[User, require(Perm.INBOX_RESPOND)],
) -> Message:
    row = await db.get(ContactMessage, message_id)
    if row is None:
        raise NotFound("No message with that id.")

    await send_email(
        db,
        to_address=row.email,
        subject=payload.subject,
        template="generic",
        context={"subject": payload.subject, "body": payload.body},
    )
    if payload.cc_team:
        await send_email(
            db,
            to_address=settings.OWNER_EMAIL,
            subject=f"[copy] {payload.subject}",
            template="generic",
            context={"subject": payload.subject, "body": payload.body},
        )

    row.status = MessageStatus.REPLIED
    row.replied_at = datetime.now(timezone.utc)
    row.reply_body = payload.body
    await db.commit()
    return Message(detail=f"Reply sent to {row.email}.")


@router.get("/inbox/requests", response_model=Page[ProjectRequestRead])
async def list_requests(
    db: DbSession,
    page: Pagination,
    _: Annotated[User, require(Perm.INBOX_READ)],
    request_status: Annotated[str | None, Query(alias="status")] = None,
    sort: str = "score",
) -> Page[ProjectRequestRead]:
    stmt = select(ProjectRequest).where(ProjectRequest.deleted_at.is_(None))
    if request_status:
        stmt = stmt.where(ProjectRequest.status == request_status)

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    order = (
        ProjectRequest.lead_score.desc()
        if sort == "score"
        else ProjectRequest.created_at.desc()
    )
    rows = (
        await db.scalars(stmt.order_by(order).offset(page.offset).limit(page.limit))
    ).all()
    return Page.build(
        [ProjectRequestRead.model_validate(row) for row in rows],
        total or 0,
        page.page,
        page.per_page,
    )


@router.patch("/inbox/requests/{request_id}", response_model=ProjectRequestRead)
async def update_request(
    request_id: int,
    payload: ProjectRequestUpdate,
    db: DbSession,
    _: Annotated[User, require(Perm.INBOX_READ)],
) -> ProjectRequest:
    row = await db.get(ProjectRequest, request_id)
    if row is None:
        raise NotFound("No brief with that id.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("quoted_amount") is not None and row.quote_sent_at is None:
        row.quote_sent_at = datetime.now(timezone.utc)
    if data.get("status") in {RequestStatus.WON, RequestStatus.LOST}:
        row.decided_at = datetime.now(timezone.utc)
    for field, value in data.items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.get("/inbox/subscribers", response_model=Page[SubscriberRead])
async def list_subscribers(
    db: DbSession,
    page: Pagination,
    _: Annotated[User, require(Perm.NEWSLETTER_MANAGE)],
    subscriber_status: Annotated[str | None, Query(alias="status")] = None,
) -> Page[SubscriberRead]:
    stmt = select(NewsletterSubscriber)
    if subscriber_status:
        stmt = stmt.where(NewsletterSubscriber.status == subscriber_status)
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(NewsletterSubscriber.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
    ).all()
    return Page.build(
        [SubscriberRead.model_validate(row) for row in rows],
        total or 0,
        page.page,
        page.per_page,
    )
