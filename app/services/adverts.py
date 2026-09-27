"""Advert selection and event recording.

Selection is a weighted random draw over the creatives eligible for a slot,
filtered by schedule, caps and targeting. Impressions and clicks are written
as rows and folded into the counters on the advert.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.advert import AdEvent, Advert, AdSlot
from app.models.enums import AdPricingModel, AdStatus
from app.schemas.payment import AdCreativeServe, AdSlotServe


def _targeting_matches(
    advert: Advert,
    *,
    category: str | None,
    tags: list[str],
    country: str | None,
    device: str | None,
    post_id: int | None,
) -> bool:
    if advert.target_categories and category not in advert.target_categories:
        return False
    if advert.target_tags and not (set(advert.target_tags) & set(tags)):
        return False
    if advert.target_countries and (country or "").upper() not in advert.target_countries:
        return False
    if advert.target_devices and device not in advert.target_devices:
        return False
    if post_id and post_id in (advert.exclude_post_ids or []):
        return False
    return True


async def _under_daily_cap(db: AsyncSession, advert: Advert) -> bool:
    if not advert.daily_impression_cap:
        return True
    today = date.today()
    used = await db.scalar(
        select(func.count(AdEvent.id)).where(
            AdEvent.advert_id == advert.id,
            AdEvent.type == "impression",
            AdEvent.day == today,
        )
    )
    return (used or 0) < advert.daily_impression_cap


async def eligible(
    db: AsyncSession,
    slot: AdSlot,
    *,
    category: str | None = None,
    tags: list[str] | None = None,
    country: str | None = None,
    device: str | None = None,
    post_id: int | None = None,
) -> list[Advert]:
    now = datetime.now(timezone.utc)
    rows = (
        await db.scalars(
            select(Advert).where(
                Advert.slot_id == slot.id,
                Advert.status.in_([AdStatus.RUNNING, AdStatus.SCHEDULED]),
                or_(Advert.starts_on.is_(None), Advert.starts_on <= now),
                or_(Advert.ends_on.is_(None), Advert.ends_on >= now),
            )
        )
    ).all()

    out: list[Advert] = []
    for advert in rows:
        if advert.impression_cap and advert.impression_count >= advert.impression_cap:
            continue
        if advert.click_cap and advert.click_count >= advert.click_cap:
            continue
        if not _targeting_matches(
            advert,
            category=category,
            tags=tags or [],
            country=country,
            device=device,
            post_id=post_id,
        ):
            continue
        if not await _under_daily_cap(db, advert):
            continue
        out.append(advert)
    return out


def pick(adverts: list[Advert], count: int = 1) -> list[Advert]:
    """Weighted draw without replacement."""
    pool = list(adverts)
    chosen: list[Advert] = []
    while pool and len(chosen) < count:
        weights = [max(1, advert.weight) for advert in pool]
        selected = random.choices(pool, weights=weights, k=1)[0]
        chosen.append(selected)
        pool.remove(selected)
    return chosen


def to_creative(advert: Advert, slot: AdSlot) -> AdCreativeServe:
    return AdCreativeServe(
        id=advert.id,
        slot_key=slot.key,
        creative_type=advert.creative_type,
        headline=advert.headline,
        body=advert.body,
        image_url=advert.image_url,
        cta_label=advert.cta_label or "Learn more",
        click_url=f"{settings.API_V1_PREFIX}/adverts/{advert.id}/click",
        html=advert.html,
        accent=advert.accent,
    )


async def serve(
    db: AsyncSession,
    slot_key: str,
    **context: object,
) -> AdSlotServe | None:
    slot = await db.scalar(select(AdSlot).where(AdSlot.key == slot_key, AdSlot.is_active))
    if slot is None:
        return None

    adverts = await eligible(db, slot, **context)  # type: ignore[arg-type]
    creatives = [to_creative(advert, slot) for advert in pick(adverts, slot.max_concurrent)]

    return AdSlotServe(
        slot_key=slot.key,
        placement=slot.placement,
        format=slot.format,
        width=slot.width,
        height=slot.height,
        creatives=creatives,
        fallback_html=slot.fallback_html if not creatives else None,
    )


def _revenue_for(advert: Advert, slot: AdSlot, event_type: str) -> int:
    """Minor units earned by one event under the slot's pricing model."""
    if slot.pricing_model == AdPricingModel.CPM and event_type == "impression":
        return round(slot.base_price_minor / 1000)
    if slot.pricing_model == AdPricingModel.CPC and event_type == "click":
        return slot.base_price_minor
    return 0


async def record_event(
    db: AsyncSession,
    advert: Advert,
    event_type: str,
    *,
    post_id: int | None = None,
    anon_key: str | None = None,
    country: str | None = None,
    device: str | None = None,
    referrer: str | None = None,
) -> AdEvent:
    slot = await db.get(AdSlot, advert.slot_id)
    revenue = _revenue_for(advert, slot, event_type) if slot else 0

    event = AdEvent(
        advert_id=advert.id,
        type=event_type,
        day=date.today(),
        post_id=post_id,
        anon_key=anon_key,
        country=country,
        device=device,
        referrer=referrer,
        revenue_minor=revenue,
    )
    db.add(event)

    if event_type == "impression":
        advert.impression_count += 1
    elif event_type == "click":
        advert.click_count += 1
    advert.spend_minor += revenue

    if advert.impression_cap and advert.impression_count >= advert.impression_cap:
        advert.status = AdStatus.COMPLETED
    if advert.ends_on and advert.ends_on < datetime.now(timezone.utc):
        advert.status = AdStatus.COMPLETED

    await db.flush()
    return event


async def activate_paid(db: AsyncSession, advert: Advert) -> Advert:
    """Move a booking forward once its payment settles."""
    advert.status = (
        AdStatus.RUNNING
        if not advert.starts_on or advert.starts_on <= datetime.now(timezone.utc)
        else AdStatus.SCHEDULED
    )
    await db.flush()
    return advert
