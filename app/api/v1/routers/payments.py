"""Checkout, webhooks, refunds and plans."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, MaybeUser, Pagination, require
from app.core.config import settings
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.permissions import Perm
from app.models.enums import NotificationKind, PaymentStatus
from app.models.payment import Payment, Plan, WebhookEvent
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.payment import (
    CheckoutCreate,
    CheckoutSession,
    PaymentRead,
    PlanRead,
    PlanWrite,
    RefundIn,
)
from app.services import notifications
from app.services.email import send_email
from app.services.payments import format_amount, get_provider, new_reference
from app.services.text import slugify

router = APIRouter(tags=["payments"])


# --------------------------------------------------------------------- plans
@router.get("/plans", response_model=list[PlanRead])
async def list_plans(db: DbSession, family: str | None = None) -> list[Plan]:
    stmt = select(Plan).where(Plan.is_active.is_(True))
    if family:
        stmt = stmt.where(Plan.family == family)
    rows = await db.scalars(stmt.order_by(Plan.position, Plan.amount_minor))
    return list(rows.all())


@router.post("/plans", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanWrite, db: DbSession, _: Annotated[User, require(Perm.SETTINGS_MANAGE)]
) -> Plan:
    plan = Plan(**payload.model_dump(exclude={"slug"}), slug=payload.slug or slugify(payload.name))
    db.add(plan)
    await db.commit()
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanRead)
async def update_plan(
    plan_id: int,
    payload: PlanWrite,
    db: DbSession,
    _: Annotated[User, require(Perm.SETTINGS_MANAGE)],
) -> Plan:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise NotFound("No plan with that id.")
    for field, value in payload.model_dump(exclude_unset=True, exclude={"slug"}).items():
        setattr(plan, field, value)
    await db.commit()
    return plan


# ------------------------------------------------------------------ checkout
@router.post("/payments/checkout", response_model=CheckoutSession)
async def start_checkout(
    payload: CheckoutCreate, db: DbSession, user: MaybeUser
) -> CheckoutSession:
    """Open a payment session with the configured provider."""
    amount = payload.amount_minor
    currency = payload.currency
    description = payload.description or "Payment"
    plan = None

    if payload.plan_slug:
        plan = await db.scalar(select(Plan).where(Plan.slug == payload.plan_slug))
        if plan is None:
            raise NotFound("No plan with that name.")
        amount, currency, description = plan.amount_minor, plan.currency, plan.name

    if not amount or amount <= 0:
        raise ValidationFailed("Give an amount, or name a plan with a price.")

    payer_email = payload.payer_email or (user.email if user else None)
    reference = new_reference()
    provider = get_provider()
    result = provider.create_checkout(
        reference=reference,
        amount_minor=amount,
        currency=currency,
        description=description,
        payer_email=payer_email,
        success_url=payload.success_url or f"{settings.SITE_URL}/payment/success",
        cancel_url=payload.cancel_url or f"{settings.SITE_URL}/payment/cancelled",
        meta=payload.meta,
    )

    db.add(
        Payment(
            reference=reference,
            provider=result.provider,
            provider_reference=result.provider_reference,
            amount_minor=amount,
            currency=currency,
            purpose=payload.purpose,
            description=description,
            user_id=user.id if user else None,
            payer_email=payer_email,
            payer_name=payload.payer_name or (user.display_name if user else None),
            plan_id=plan.id if plan else None,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            checkout_url=result.checkout_url,
            provider_payload=result.raw,
            meta=payload.meta,
        )
    )
    await db.commit()

    return CheckoutSession(
        reference=reference,
        checkout_url=result.checkout_url,
        provider=result.provider,
        amount_minor=amount,
        currency=currency,
    )


@router.get("/payments/{reference}", response_model=PaymentRead)
async def read_payment(reference: str, db: DbSession, user: MaybeUser) -> Payment:
    payment = await db.scalar(select(Payment).where(Payment.reference == reference))
    if payment is None:
        raise NotFound("No payment with that reference.")
    # A payer sees their own; staff see all.
    if payment.user_id and user and payment.user_id != user.id:
        if not user.has_permission(Perm.PAYMENT_READ):
            raise NotFound("No payment with that reference.")
    return payment


@router.get("/payments", response_model=Page[PaymentRead])
async def list_payments(
    db: DbSession,
    page: Pagination,
    _: Annotated[User, require(Perm.PAYMENT_READ)],
    payment_status: str | None = None,
    purpose: str | None = None,
) -> Page[PaymentRead]:
    stmt = select(Payment)
    if payment_status:
        stmt = stmt.where(Payment.status == payment_status)
    if purpose:
        stmt = stmt.where(Payment.purpose == purpose)
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(Payment.created_at.desc()).offset(page.offset).limit(page.limit)
        )
    ).all()
    return Page.build(
        [PaymentRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
    )


async def _settle(db: DbSession, payment: Payment, event) -> None:
    """Mark a payment paid and run whatever the payment unlocks."""
    if payment.status == PaymentStatus.SUCCEEDED:
        return
    payment.status = PaymentStatus.SUCCEEDED
    payment.paid_at = datetime.now(timezone.utc)
    payment.fee_minor = event.fee_minor or payment.fee_minor
    payment.provider_reference = event.provider_reference or payment.provider_reference

    if payment.subject_type == "advert" and payment.subject_id:
        from app.models.advert import Advert
        from app.services.adverts import activate_paid

        advert = await db.get(Advert, payment.subject_id)
        if advert is not None:
            await activate_paid(db, advert)

    if payment.payer_email:
        await send_email(
            db,
            to_address=payment.payer_email,
            template="payment_receipt",
            context={
                "name": payment.payer_name or "there",
                "amount": format_amount(payment.amount_minor, payment.currency),
                "description": payment.description or "payment",
                "reference": payment.reference,
            },
        )
    if payment.user_id:
        await notifications.notify(
            db,
            recipient=payment.user_id,
            kind=NotificationKind.PAYMENT_RECEIVED,
            title=f"Payment of {format_amount(payment.amount_minor, payment.currency)} received",
            url=f"/payment/{payment.reference}",
            subject_type="payment",
            subject_id=payment.id,
        )
    await notifications.notify_permission_holders(
        db,
        Perm.PAYMENT_READ,
        kind=NotificationKind.PAYMENT_RECEIVED,
        title=f"{format_amount(payment.amount_minor, payment.currency)} received",
        body=payment.description,
        url=f"/dashboard/payments/{payment.reference}",
        subject_type="payment",
        subject_id=payment.id,
    )


@router.post("/payments/webhook/{provider_name}", response_model=Message)
async def payment_webhook(
    provider_name: str,
    request: Request,
    db: DbSession,
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
    paystack_signature: Annotated[str | None, Header(alias="x-paystack-signature")] = None,
    flutterwave_signature: Annotated[str | None, Header(alias="verif-hash")] = None,
    mock_signature: Annotated[str | None, Header(alias="x-mock-signature")] = None,
) -> Message:
    """Provider callback. Signature-checked and idempotent."""
    raw = await request.body()
    provider = get_provider(provider_name)
    signature = stripe_signature or paystack_signature or flutterwave_signature or mock_signature

    if not provider.verify_signature(raw, signature):
        raise ValidationFailed("That webhook signature does not check out.")

    event = provider.parse_event(json.loads(raw or b"{}"))

    seen = await db.scalar(
        select(WebhookEvent).where(
            WebhookEvent.provider == provider_name, WebhookEvent.event_id == event.event_id
        )
    )
    if seen is not None:
        return Message(detail="Already processed.", code="duplicate")

    record = WebhookEvent(
        provider=provider_name,
        event_id=event.event_id,
        event_type=event.event_type,
        payload=event.raw,
    )
    db.add(record)

    payment = None
    if event.reference:
        payment = await db.scalar(select(Payment).where(Payment.reference == event.reference))

    if payment is not None:
        if event.event_type == "payment.succeeded":
            await _settle(db, payment, event)
        elif event.event_type == "payment.failed":
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = event.failure_reason
            if payment.user_id:
                await notifications.notify(
                    db,
                    recipient=payment.user_id,
                    kind=NotificationKind.PAYMENT_FAILED,
                    title="A payment did not go through",
                    body=event.failure_reason,
                    subject_type="payment",
                    subject_id=payment.id,
                )
        elif event.event_type == "payment.refunded":
            payment.refunded_minor = event.amount_minor or payment.amount_minor
            payment.status = (
                PaymentStatus.REFUNDED
                if payment.refunded_minor >= payment.amount_minor
                else PaymentStatus.PARTIALLY_REFUNDED
            )

    record.processed_at = datetime.now(timezone.utc)
    await db.commit()
    return Message(detail="Processed.")


@router.post("/payments/{reference}/simulate", response_model=PaymentRead)
async def simulate_payment(
    reference: str, db: DbSession, user: CurrentUser, succeed: bool = True
) -> Payment:
    """Settle a mock payment without a provider. Development only."""
    if settings.is_production or settings.PAYMENT_PROVIDER != "mock":
        raise Conflict("Simulation is only available with the mock provider.")

    payment = await db.scalar(select(Payment).where(Payment.reference == reference))
    if payment is None:
        raise NotFound("No payment with that reference.")

    if succeed:
        from app.services.payments import NormalisedEvent

        await _settle(
            db,
            payment,
            NormalisedEvent(
                event_id=f"sim_{reference}",
                event_type="payment.succeeded",
                reference=reference,
                provider_reference=payment.provider_reference,
                amount_minor=payment.amount_minor,
                currency=payment.currency,
            ),
        )
    else:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Simulated failure"

    await db.commit()
    return payment


@router.post("/payments/{reference}/refund", response_model=PaymentRead)
async def refund(
    reference: str,
    payload: RefundIn,
    db: DbSession,
    _: Annotated[User, require(Perm.PAYMENT_REFUND)],
) -> Payment:
    payment = await db.scalar(select(Payment).where(Payment.reference == reference))
    if payment is None:
        raise NotFound("No payment with that reference.")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise Conflict("Only a settled payment can be refunded.")

    amount = payload.amount_minor or (payment.amount_minor - payment.refunded_minor)
    if amount <= 0 or amount > payment.amount_minor - payment.refunded_minor:
        raise ValidationFailed("That refund amount is more than what is left to refund.")

    payment.refunded_minor += amount
    payment.status = (
        PaymentStatus.REFUNDED
        if payment.refunded_minor >= payment.amount_minor
        else PaymentStatus.PARTIALLY_REFUNDED
    )
    payment.meta = {**payment.meta, "refund_reason": payload.reason}
    await db.commit()
    return payment
