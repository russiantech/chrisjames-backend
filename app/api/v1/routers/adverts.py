"""Advert slots, bookings, serving and click tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.api.deps import (
    AnonKey,
    CurrentUser,
    DbSession,
    Pagination,
    request_country,
    request_device,
    require,
)
from app.core.exceptions import NotFound, PermissionDenied
from app.core.permissions import Perm
from app.models.advert import Advert, AdSlot, Sponsor
from app.models.enums import AdStatus, NotificationKind
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.payment import (
    AdSlotRead,
    AdSlotServe,
    AdSlotUpdate,
    AdSlotWrite,
    AdvertCreate,
    AdvertDecision,
    AdvertRead,
    AdvertUpdate,
)
from app.services import adverts as service, notifications, settings_store

router = APIRouter(tags=["adverts"])


# --------------------------------------------------------------------- serve
@router.get("/ad-slots/{slot_key}/serve", response_model=AdSlotServe | None)
async def serve_slot(
    slot_key: str,
    request: Request,
    db: DbSession,
    anon: AnonKey,
    category: str | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    post_id: Annotated[int | None, Query(alias="postId")] = None,
) -> AdSlotServe | None:
    """What to render in one slot, for this reader, on this page."""
    if not await settings_store.get_setting(db, "ads_enabled", True):
        return None

    result = await service.serve(
        db,
        slot_key,
        category=category,
        tags=tags or [],
        country=request_country(request),
        device=request_device(request),
        post_id=post_id,
    )
    if result is None:
        return None

    for creative in result.creatives:
        advert = await db.get(Advert, creative.id)
        if advert is not None:
            await service.record_event(
                db,
                advert,
                "impression",
                post_id=post_id,
                anon_key=anon,
                country=request_country(request),
                device=request_device(request),
            )
    await db.commit()
    return result


@router.get("/adverts/{advert_id}/click")
async def click_through(
    advert_id: int, request: Request, db: DbSession, anon: AnonKey
) -> RedirectResponse:
    """Count the click, then bounce the reader to the advertiser."""
    advert = await db.get(Advert, advert_id)
    if advert is None:
        raise NotFound("That advert is no longer running.")

    await service.record_event(
        db,
        advert,
        "click",
        anon_key=anon,
        country=request_country(request),
        device=request_device(request),
        referrer=request.headers.get("referer"),
    )
    await db.commit()
    return RedirectResponse(advert.target_url, status_code=status.HTTP_302_FOUND)


@router.get("/sponsors", response_model=list[dict])
async def list_sponsors(db: DbSession) -> list[dict]:
    """Logos for the "trusted by" rail."""
    rows = await db.scalars(
        select(Sponsor).where(Sponsor.is_active.is_(True)).order_by(Sponsor.position)
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "logo_url": row.logo_url,
            "website": row.website,
            "tier": row.tier,
            "opacity": row.opacity,
        }
        for row in rows.all()
    ]


# --------------------------------------------------------------------- slots
@router.get("/ad-slots", response_model=list[AdSlotRead])
async def list_slots(db: DbSession, active_only: bool = True) -> list[AdSlot]:
    stmt = select(AdSlot)
    if active_only:
        stmt = stmt.where(AdSlot.is_active.is_(True))
    rows = await db.scalars(stmt.order_by(AdSlot.placement, AdSlot.key))
    return list(rows.all())


@router.post("/ad-slots", response_model=AdSlotRead, status_code=status.HTTP_201_CREATED)
async def create_slot(
    payload: AdSlotWrite, db: DbSession, _: Annotated[User, require(Perm.AD_MANAGE)]
) -> AdSlot:
    slot = AdSlot(**payload.model_dump())
    db.add(slot)
    await db.commit()
    return slot


@router.patch("/ad-slots/{slot_id}", response_model=AdSlotRead)
async def update_slot(
    slot_id: int,
    payload: AdSlotUpdate,
    db: DbSession,
    _: Annotated[User, require(Perm.AD_MANAGE)],
) -> AdSlot:
    slot = await db.get(AdSlot, slot_id)
    if slot is None:
        raise NotFound("No slot with that id.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)
    await db.commit()
    return slot


# ------------------------------------------------------------------ bookings
@router.post("/adverts", response_model=AdvertRead, status_code=status.HTTP_201_CREATED)
async def book_advert(
    payload: AdvertCreate,
    db: DbSession,
    user: Annotated[User, require(Perm.AD_PURCHASE, Perm.AD_MANAGE)],
) -> Advert:
    """Create a booking. It runs once paid for and approved."""
    slot = await db.get(AdSlot, payload.slot_id)
    if slot is None or not slot.is_active:
        raise NotFound("No slot with that id.")

    advert = Advert(
        **payload.model_dump(),
        advertiser_id=user.id,
        status=(
            AdStatus.PENDING_REVIEW
            if user.has_permission(Perm.AD_MANAGE)
            else AdStatus.PENDING_PAYMENT
        ),
    )
    db.add(advert)
    await db.flush()

    await notifications.notify_permission_holders(
        db,
        Perm.AD_MANAGE,
        kind=NotificationKind.SYSTEM,
        title=f"New advert booking: {advert.name}",
        body=f"{user.display_name} booked the {slot.name} slot.",
        url=f"/dashboard/adverts/{advert.id}",
        actor=user,
        subject_type="advert",
        subject_id=advert.id,
    )
    await db.commit()
    return advert


@router.get("/adverts", response_model=Page[AdvertRead])
async def list_adverts(
    db: DbSession,
    page: Pagination,
    user: CurrentUser,
    advert_status: Annotated[str | None, Query(alias="status")] = None,
    slot_id: int | None = None,
) -> Page[AdvertRead]:
    stmt = select(Advert)
    # Advertisers only ever see their own bookings.
    if not user.has_permission(Perm.AD_MANAGE):
        stmt = stmt.where(Advert.advertiser_id == user.id)
    if advert_status:
        stmt = stmt.where(Advert.status == advert_status)
    if slot_id:
        stmt = stmt.where(Advert.slot_id == slot_id)

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(Advert.created_at.desc()).offset(page.offset).limit(page.limit)
        )
    ).all()
    return Page.build(
        [AdvertRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
    )


@router.patch("/adverts/{advert_id}", response_model=AdvertRead)
async def update_advert(
    advert_id: int, payload: AdvertUpdate, db: DbSession, user: CurrentUser
) -> Advert:
    advert = await db.get(Advert, advert_id)
    if advert is None:
        raise NotFound("No advert with that id.")

    manages = user.has_permission(Perm.AD_MANAGE)
    if advert.advertiser_id != user.id and not manages:
        raise PermissionDenied("You can only edit your own bookings.")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data and not manages:
        # An advertiser may pause or resume, nothing more.
        if data["status"] not in {AdStatus.PAUSED, AdStatus.RUNNING}:
            raise PermissionDenied("Only the site owner can set that status.")

    for field, value in data.items():
        setattr(advert, field, value)

    if not manages and advert.status == AdStatus.RUNNING:
        # An edited creative goes back through review.
        advert.status = AdStatus.PENDING_REVIEW

    await db.commit()
    return advert


@router.post("/adverts/{advert_id}/review", response_model=Message)
async def review_advert(
    advert_id: int,
    payload: AdvertDecision,
    db: DbSession,
    user: Annotated[User, require(Perm.AD_MANAGE)],
) -> Message:
    advert = await db.get(Advert, advert_id)
    if advert is None:
        raise NotFound("No advert with that id.")

    advert.reviewed_by_id = user.id
    advert.reviewed_at = datetime.now(timezone.utc)

    if payload.approve:
        await service.activate_paid(db, advert)
        message = "Approved. It starts serving on schedule."
        kind, title = NotificationKind.AD_APPROVED, f"“{advert.name}” was approved"
    else:
        advert.status = AdStatus.REJECTED
        advert.rejection_reason = payload.reason
        message = "Rejected. The advertiser has been told why."
        kind, title = NotificationKind.SYSTEM, f"“{advert.name}” was not approved"

    if advert.advertiser_id:
        await notifications.notify(
            db,
            recipient=advert.advertiser_id,
            kind=kind,
            title=title,
            body=payload.reason,
            url=f"/dashboard/adverts/{advert.id}",
            actor=user,
            subject_type="advert",
            subject_id=advert.id,
        )
    await db.commit()
    return Message(detail=message)


@router.delete("/adverts/{advert_id}", response_model=Message)
async def cancel_advert(advert_id: int, db: DbSession, user: CurrentUser) -> Message:
    advert = await db.get(Advert, advert_id)
    if advert is None:
        raise NotFound("No advert with that id.")
    if advert.advertiser_id != user.id and not user.has_permission(Perm.AD_MANAGE):
        raise PermissionDenied("You can only cancel your own bookings.")
    advert.status = AdStatus.COMPLETED
    await db.commit()
    return Message(detail="Booking cancelled.")
