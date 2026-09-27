"""Runtime settings, read from the database with a fallback to the env config.

Anything in ``site_settings`` overrides the matching attribute on the frozen
``Settings`` object, which is how the auto-publish switch and comment policy
can be changed from the dashboard without a redeploy.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.portfolio import SiteSetting

#: key → (env attribute, type, group, label, public?)
DEFINITIONS: dict[str, tuple[str | None, str, str, str, bool]] = {
    "auto_publish_submissions": (
        "AUTO_PUBLISH_SUBMISSIONS", "bool", "moderation",
        "Publish visitor submissions automatically", False,
    ),
    "auto_approve_comments": (
        "AUTO_APPROVE_COMMENTS", "bool", "moderation",
        "Show new comments immediately", True,
    ),
    "comments_require_login": (
        "COMMENTS_REQUIRE_LOGIN", "bool", "moderation",
        "Require an account to comment", True,
    ),
    "guest_posts_enabled": (
        None, "bool", "moderation", "Accept posts from signed-out visitors", True,
    ),
    "comment_report_threshold": (
        None, "int", "moderation", "Reports before a comment is auto-hidden", False,
    ),
    "site_title": (None, "string", "general", "Site title", True),
    "site_tagline": (None, "string", "general", "Tagline", True),
    "available_for_work": (None, "bool", "general", "Show the availability badge", True),
    "ads_enabled": (None, "bool", "adverts", "Serve adverts", True),
    "newsletter_enabled": (None, "bool", "general", "Show the newsletter form", True),
    "payments_enabled": (None, "bool", "payments", "Accept payments", True),
}

DEFAULTS: dict[str, Any] = {
    "guest_posts_enabled": True,
    "comment_report_threshold": 3,
    "site_title": "Christopher James",
    "site_tagline": "Software engineer. AI, data and security.",
    "available_for_work": True,
    "ads_enabled": True,
    "newsletter_enabled": True,
    "payments_enabled": True,
}


async def get_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    row = await db.scalar(select(SiteSetting).where(SiteSetting.key == key))
    if row is not None:
        return row.value
    env_attr = DEFINITIONS.get(key, (None,))[0]
    if env_attr and hasattr(settings, env_attr):
        return getattr(settings, env_attr)
    return DEFAULTS.get(key, default)


async def get_many(db: AsyncSession, *keys: str) -> dict[str, Any]:
    rows = (
        await db.scalars(select(SiteSetting).where(SiteSetting.key.in_(keys)))
    ).all()
    found = {row.key: row.value for row in rows}
    out: dict[str, Any] = {}
    for key in keys:
        if key in found:
            out[key] = found[key]
        else:
            env_attr = DEFINITIONS.get(key, (None,))[0]
            out[key] = (
                getattr(settings, env_attr)
                if env_attr and hasattr(settings, env_attr)
                else DEFAULTS.get(key)
            )
    return out


async def set_setting(db: AsyncSession, key: str, value: Any) -> SiteSetting:
    row = await db.scalar(select(SiteSetting).where(SiteSetting.key == key))
    meta = DEFINITIONS.get(key)
    if row is None:
        row = SiteSetting(
            key=key,
            value=value,
            value_type=meta[1] if meta else "json",
            group=meta[2] if meta else "general",
            label=meta[3] if meta else key.replace("_", " ").capitalize(),
            is_public=meta[4] if meta else False,
        )
        db.add(row)
    else:
        row.value = value
    await db.flush()
    return row


async def public_settings(db: AsyncSession) -> dict[str, Any]:
    keys = [k for k, meta in DEFINITIONS.items() if meta[4]]
    return await get_many(db, *keys)
