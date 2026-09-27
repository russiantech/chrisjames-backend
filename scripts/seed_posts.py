"""
Seed script for blog posts, matching `app/models/post.py` (Post +
ContentBlock) and the `/posts` router in `app/api/posts.py` exactly.

WHY THIS ONE TALKS TO THE API INSTEAD OF THE DATABASE
-------------------------------------------------------
seed_portfolio.py (projects/experience/skills/services) writes straight to
the DB because those are plain tables with no real business logic attached.
Posts are different — `create_post` in your router does several things a
raw INSERT would skip or get wrong:
  - `service.unique_slug(...)` — collision-safe slugging
  - `service.sync_tags(...)` / `service.sync_blocks(...)` — the actual
    tag/block relationship wiring (junction rows, positions, etc.)
  - `service.apply_status(...)` — the real publish transition, including
    whatever side effects it triggers (published_at, indexing, etc.)
Re-implementing all of that against the ORM directly would be guessing at
internals we can't see from here. Calling the endpoint you already wrote
and tested is the safe way to seed this one.

WHAT'S MISSING RIGHT NOW
-------------------------
POSTS below is empty. I could not pull your actual LinkedIn posts — LinkedIn
blocks automated/robots access to profile activity (no login, no public
API for post content), and I'm not going to invent posts and put your name
on them. What I need from you, per post:
  - the raw text
  - any image URL(s) used in it (or tell me "text only")
  - the 2–4 tags you'd file it under
Paste those (up to the 10–15 you want seeded) and I'll turn each one into
a POSTS entry below in the exact block/tag shape the router expects —
nothing omitted, same as every other post here.

USAGE
-----
    AUTH_TOKEN=<admin bearer token> python seed_posts.py
    AUTH_TOKEN=<admin bearer token> API_BASE=https://api.techa.example/api/v1 python seed_posts.py

Idempotent the same way create_post's own slugging is: re-running with a
post whose slug already exists will 409/slug-collide rather than duplicate
it (service.unique_slug appends a suffix instead) — check output before
assuming a clean re-run == no-op.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

API_BASE = os.environ.get("API_BASE", "http://localhost:8000/api/v1")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")


# --------------------------------------------------------------------------
# posts — one dict per post, matching PostCreate + the ContentBlock shapes
# documented in app/models/post.py. Fill in via the note above.
# --------------------------------------------------------------------------
POSTS: list[dict[str, Any]] = [
    # Shape reference — copy this for each real post, delete once real
    # entries are in:
    #
    # {
    #     "title": "Shipping an AI-assisted LMS in six weeks",
    #     "slug": "shipping-an-ai-assisted-lms-in-six-weeks",
    #     "subtitle": None,
    #     "excerpt": "One-paragraph summary shown in the feed and previews.",
    #     "cover_url": "https://.../cover.jpg",  # or None for text-only
    #     "cover_caption": None,
    #     "tags": ["fastapi", "react", "edtech"],
    #     "category_id": None,
    #     "visibility": "public",
    #     "allow_comments": True,
    #     "allow_reactions": True,
    #     "show_ads": True,
    #     "language": "en",
    #     "status": "published",
    #     "blocks": [
    #         {"type": "rich_text", "data": {"html": "<p>The actual post body…</p>"}},
    #         {"type": "image", "data": {"url": "https://.../inline.jpg", "alt": "…"}},
    #     ],
    # },
]


async def seed_posts(client: httpx.AsyncClient) -> None:
    if not POSTS:
        print(
            "POSTS is empty — nothing to seed yet. See the module docstring "
            "for what's needed from you before this can run for real."
        )
        return

    for post in POSTS:
        response = await client.post("/posts", json=post)
        if response.status_code >= 400:
            print(f"  ! {post['slug']}: {response.status_code} {response.text}")
            continue
        print(f"  ✓ {post['slug']}")


async def run() -> None:
    if not AUTH_TOKEN:
        print(
            "AUTH_TOKEN is not set — export an admin bearer token first "
            "(create_post requires POST_CREATE permission)."
        )
        return

    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    async with httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=30) as client:
        print(f"Seeding posts against {API_BASE} …")
        await seed_posts(client)


if __name__ == "__main__":
    asyncio.run(run())

