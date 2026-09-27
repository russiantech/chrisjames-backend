"""End-to-end coverage of the main flows."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio
API = "/api/v1"


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_seeded_public_content(client):
    posts = (await client.get(f"{API}/posts")).json()
    assert posts["total"] >= 1

    services = (await client.get(f"{API}/services")).json()
    assert len(services) == 4

    projects = (await client.get(f"{API}/projects")).json()
    assert any(project["slug"] == "intellect" for project in projects)

    plans = (await client.get(f"{API}/plans")).json()
    assert any(plan["slug"] == "sprint" for plan in plans)


async def test_login_and_me(client, auth):
    me = (await client.get(f"{API}/auth/me", headers=auth)).json()
    assert me["username"] == "chrisjames"
    assert me["is_superuser"] is True
    assert "post:publish" in me["permissions"]


async def test_bad_login_is_vague(client):
    response = await client.post(
        f"{API}/auth/login", json={"identifier": "admin@chrisjames.dev", "password": "wrong"}
    )
    assert response.status_code == 401
    # Must not reveal whether the account exists.
    assert "password" in response.json()["detail"].lower()


async def test_register_and_permission_boundary(client):
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": "reader@example.com",
            "username": "reader",
            "password": "ReaderPass123",
            "full_name": "Sam Reader",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "pending"

    # A pending account cannot sign in until the address is confirmed.
    login = await client.post(
        f"{API}/auth/login",
        json={"identifier": "reader@example.com", "password": "ReaderPass123"},
    )
    assert login.status_code == 401


async def test_weak_password_rejected(client):
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "weak@example.com", "username": "weakling", "password": "alllowercase"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


async def test_create_post_with_every_block_type(client, auth):
    payload = {
        "title": "A post with mixed media",
        "status": "published",
        "tags": ["testing", "blocks"],
        "blocks": [
            {"type": "rich_text", "data": {"html": "<p>Intro paragraph.</p>"}},
            {"type": "heading", "data": {"text": "The code", "level": 2}},
            {
                "type": "code",
                "data": {
                    "language": "python",
                    "source": "def hello():\n    return 'world'",
                    "filename": "hello.py",
                },
            },
            {"type": "image", "data": {"url": "/assets/img/techa_hero.png", "alt": "Hero"}},
            {"type": "video", "data": {"url": "https://example.com/v.mp4", "provider": "upload"}},
            {"type": "audio", "data": {"url": "https://example.com/a.mp3"}},
            {"type": "quote", "data": {"text": "Make it work, then make it fast."}},
            {
                "type": "poll",
                "data": {},
                "poll": {
                    "question": "Which stack would you pick?",
                    "options": [{"label": "FastAPI"}, {"label": "Django"}, {"label": "Node"}],
                    "hide_results_until_voted": True,
                },
            },
            {"type": "ad_slot", "data": {"slot_key": "in_article_1"}},
            {"type": "divider", "data": {}},
        ],
    }
    response = await client.post(f"{API}/posts", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    post = response.json()

    assert post["status"] == "published"
    assert len(post["blocks"]) == 10
    assert len(post["polls"]) == 1
    assert post["word_count"] > 0

    code_block = next(b for b in post["blocks"] if b["type"] == "code")
    # Highlighting happens on write, so reads need no rendering work.
    assert "cj-code" in code_block["data"]["html"]

    return post


async def test_block_validation_rejects_incomplete_payload(client, auth):
    response = await client.post(
        f"{API}/posts",
        json={"title": "Broken post", "blocks": [{"type": "code", "data": {}}]},
        headers=auth,
    )
    assert response.status_code == 422


async def test_poll_voting_and_result_hiding(client, auth):
    post = (await client.get(f"{API}/posts/a-post-with-mixed-media")).json()
    poll = post["polls"][0]

    # Results are withheld before voting.
    assert poll["results_visible"] is False
    assert all(option["vote_count"] == 0 for option in poll["options"])

    option_id = poll["options"][0]["id"]
    voted = (
        await client.post(f"{API}/polls/{poll['id']}/vote", json={"option_ids": [option_id]})
    ).json()

    assert voted["results_visible"] is True
    assert voted["my_votes"] == [option_id]
    assert voted["total_votes"] == 1
    assert voted["options"][0]["percentage"] == 100.0

    # A second vote from the same reader replaces the first, not adds to it.
    other_id = poll["options"][1]["id"]
    changed = (
        await client.post(f"{API}/polls/{poll['id']}/vote", json={"option_ids": [other_id]})
    ).json()
    assert changed["total_votes"] == 1
    assert changed["my_votes"] == [other_id]


async def test_single_choice_poll_rejects_multiple(client):
    post = (await client.get(f"{API}/posts/a-post-with-mixed-media")).json()
    poll = post["polls"][0]
    ids = [option["id"] for option in poll["options"][:2]]
    response = await client.post(f"{API}/polls/{poll['id']}/vote", json={"option_ids": ids})
    assert response.status_code == 422


async def test_guest_submission_enters_review_queue(client, auth):
    response = await client.post(
        f"{API}/posts/submit",
        json={
            "title": "A visitor writes in",
            "guest_name": "Jane Visitor",
            "guest_email": "jane@example.com",
            "blocks": [{"type": "markdown", "data": {"source": "Hello from **outside**."}}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["code"] == "submitted"

    queue = (await client.get(f"{API}/posts/review/queue", headers=auth)).json()
    assert any(item["title"] == "A visitor writes in" for item in queue["items"])

    # It is not public while it waits.
    public = (await client.get(f"{API}/posts")).json()
    assert not any(item["title"] == "A visitor writes in" for item in public["items"])


async def test_auto_publish_switch_changes_submission_route(client, auth):
    await client.put(f"{API}/settings", json={"auto_publish_submissions": True}, headers=auth)

    response = await client.post(
        f"{API}/posts/submit",
        json={
            "title": "Straight to the front page",
            "guest_name": "Auto Author",
            "guest_email": "auto@example.com",
            "blocks": [{"type": "markdown", "data": {"source": "Live immediately."}}],
        },
    )
    assert response.json()["code"] == "published"

    await client.put(f"{API}/settings", json={"auto_publish_submissions": False}, headers=auth)


async def test_review_approves_and_publishes(client, auth):
    queue = (await client.get(f"{API}/posts/review/queue", headers=auth)).json()
    post_id = queue["items"][0]["id"]

    response = await client.post(
        f"{API}/posts/{post_id}/review", json={"approve": True, "publish": True}, headers=auth
    )
    assert response.status_code == 200
    assert "Published" in response.json()["detail"]


async def test_comment_thread_with_replies(client, auth):
    post = (await client.get(f"{API}/posts/a-post-with-mixed-media")).json()
    post_id = post["id"]

    root = await client.post(
        f"{API}/posts/{post_id}/comments",
        json={"body": "Good write-up. One question about the `code` block."},
        headers=auth,
    )
    assert root.status_code == 201, root.text
    root_id = root.json()["id"]
    assert "<code>" in root.json()["body_html"]

    reply = await client.post(
        f"{API}/posts/{post_id}/comments",
        json={
            "body": "Thanks @chrisjames — happy to explain.",
            "parent_id": root_id,
            "guest_name": "Curious Reader",
            "guest_email": "curious@example.com",
        },
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["depth"] == 1
    assert "chrisjames" in reply.json()["mentions"]

    tree = (await client.get(f"{API}/posts/{post_id}/comments")).json()
    assert len(tree) == 1
    assert len(tree[0]["replies"]) == 1
    assert tree[0]["replies"][0]["parent_id"] == root_id

    flat = (await client.get(f"{API}/posts/{post_id}/comments?flat=true")).json()
    assert len(flat) == 2


async def test_comment_markdown_is_sanitised(client, auth):
    post = (await client.get(f"{API}/posts/a-post-with-mixed-media")).json()
    response = await client.post(
        f"{API}/posts/{post['id']}/comments",
        json={"body": "<script>alert(1)</script> and an onclick attempt."},
        headers=auth,
    )
    assert response.status_code == 201
    assert "<script>" not in response.json()["body_html"]


async def test_spam_comment_is_held(client):
    post = (await client.get(f"{API}/posts/a-post-with-mixed-media")).json()
    response = await client.post(
        f"{API}/posts/{post['id']}/comments",
        json={
            "body": "buy viagra now http://a.com http://b.com http://c.com casino",
            "guest_name": "Spam Bot",
            "guest_email": "spam@example.com",
        },
    )
    assert response.status_code == 201
    assert response.json()["moderation_state"] != "approved"


async def test_reactions_toggle(client, auth):
    post = (await client.get(f"{API}/posts/a-post-with-mixed-media")).json()
    post_id = post["id"]

    first = (
        await client.post(f"{API}/posts/{post_id}/reactions", json={"type": "love"}, headers=auth)
    ).json()
    assert first["my_reaction"] == "love"
    assert first["total"] == 1

    again = (
        await client.post(f"{API}/posts/{post_id}/reactions", json={"type": "love"}, headers=auth)
    ).json()
    assert again["my_reaction"] is None
    assert again["total"] == 0


async def test_contact_form_and_inbox(client, auth):
    response = await client.post(
        f"{API}/contact",
        json={
            "name": "Prospective Client",
            "email": "client@example.com",
            "subject": "Rebuilding our dispatch system",
            "message": "We have an old PHP system and need it rebuilt. Can we talk about scope?",
        },
    )
    assert response.status_code == 201

    inbox = (await client.get(f"{API}/inbox/messages", headers=auth)).json()
    assert inbox["total"] == 1
    assert inbox["items"][0]["status"] == "unread"


async def test_honeypot_silently_absorbs_bots(client, auth):
    await client.post(
        f"{API}/contact",
        json={
            "name": "Bot",
            "email": "bot@example.com",
            "subject": "Cheap SEO services",
            "message": "Visit our site for cheap backlinks and more traffic today.",
            "website_url": "http://spam.example",
        },
    )
    inbox = (await client.get(f"{API}/inbox/messages", headers=auth)).json()
    # Nothing was stored, but the bot got a 200.
    assert inbox["total"] == 1


async def test_project_request_is_scored(client, auth):
    response = await client.post(
        f"{API}/requests",
        json={
            "name": "Ada Founder",
            "email": "ada@startup.com",
            "company": "Startup Ltd",
            "phone": "+2348000000000",
            "project_title": "AI-assisted document review",
            "summary": "We process thousands of contracts a month by hand. " * 10,
            "service_types": ["ai", "automation"],
            "budget_min": 20000,
            "budget_max": 50000,
            "timeline": "asap",
        },
    )
    assert response.status_code == 201
    assert response.json()["reference"].startswith("REQ-")

    requests = (await client.get(f"{API}/inbox/requests", headers=auth)).json()
    assert requests["items"][0]["lead_score"] >= 60


async def test_notifications_reached_the_owner(client, auth):
    counts = (await client.get(f"{API}/notifications/counts", headers=auth)).json()
    assert counts["unread"] > 0
    assert "contact_message" in counts["by_kind"]
    assert "project_request" in counts["by_kind"]

    inbox = (await client.get(f"{API}/notifications", headers=auth)).json()
    assert inbox["total"] > 0

    marked = await client.post(f"{API}/notifications/read", json={"ids": [], "read": True}, headers=auth)
    assert marked.status_code == 200

    after = (await client.get(f"{API}/notifications/counts", headers=auth)).json()
    assert after["unread"] == 0


async def test_payment_checkout_and_settlement(client, auth):
    checkout = (
        await client.post(
            f"{API}/payments/checkout",
            json={"plan_slug": "sprint", "purpose": "project_deposit"},
            headers=auth,
        )
    ).json()
    assert checkout["amount_minor"] == 350000
    reference = checkout["reference"]

    pending = (await client.get(f"{API}/payments/{reference}", headers=auth)).json()
    assert pending["status"] == "pending"

    settled = (
        await client.post(f"{API}/payments/{reference}/simulate", headers=auth)
    ).json()
    assert settled["status"] == "succeeded"
    assert settled["amount"] == 3500.0


async def test_advert_booking_serving_and_click(client, auth):
    slots = (await client.get(f"{API}/ad-slots")).json()
    slot = next(s for s in slots if s["key"] == "sidebar_primary")

    booking = await client.post(
        f"{API}/adverts",
        json={
            "slot_id": slot["id"],
            "name": "Test campaign",
            "headline": "Ship faster",
            "body": "Managed Postgres for teams that would rather build.",
            "cta_label": "Start free",
            "target_url": "https://example.com/offer",
        },
        headers=auth,
    )
    assert booking.status_code == 201, booking.text
    advert_id = booking.json()["id"]

    # Nothing serves until it is approved.
    before = (await client.get(f"{API}/ad-slots/sidebar_primary/serve")).json()
    assert before["creatives"] == []
    assert before["fallback_html"] is not None

    await client.post(f"{API}/adverts/{advert_id}/review", json={"approve": True}, headers=auth)

    after = (await client.get(f"{API}/ad-slots/sidebar_primary/serve")).json()
    assert len(after["creatives"]) == 1
    assert after["creatives"][0]["headline"] == "Ship faster"

    click = await client.get(f"{API}/adverts/{advert_id}/click", follow_redirects=False)
    assert click.status_code == 302
    assert click.headers["location"] == "https://example.com/offer"

    listed = (await client.get(f"{API}/adverts", headers=auth)).json()
    advert = next(a for a in listed["items"] if a["id"] == advert_id)
    assert advert["impression_count"] >= 1
    assert advert["click_count"] == 1


async def test_ads_can_be_switched_off_globally(client, auth):
    await client.put(f"{API}/settings", json={"ads_enabled": False}, headers=auth)
    response = await client.get(f"{API}/ad-slots/sidebar_primary/serve")
    assert response.json() is None
    await client.put(f"{API}/settings", json={"ads_enabled": True}, headers=auth)


async def test_role_permissions_are_enforced(client, auth):
    roles = (await client.get(f"{API}/roles", headers=auth)).json()
    assert {role["name"] for role in roles} >= {"owner", "editor", "author", "member"}

    editor = next(role for role in roles if role["name"] == "editor")
    assert "post:publish" in editor["permissions"]

    member = next(role for role in roles if role["name"] == "member")
    assert "post:publish" not in member["permissions"]
    assert "post:create" not in member["permissions"]


async def test_anonymous_cannot_reach_the_dashboard(client):
    for path in ("/dashboard/overview", "/admin/users", "/settings", "/posts/review/queue"):
        response = await client.get(f"{API}{path}")
        assert response.status_code in (401, 403), path


async def test_search_across_content(client):
    response = await client.get(f"{API}/search?q=blocks")
    assert response.status_code == 200
    assert len(response.json()["posts"]) >= 1


async def test_dashboard_overview(client, auth):
    data = (await client.get(f"{API}/dashboard/overview", headers=auth)).json()
    assert data["counters"]["published_posts"] >= 2
    assert data["revenue_30d_minor"] == 350000


async def test_error_envelope_shape(client):
    response = await client.get(f"{API}/posts/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found"
    assert "request_id" in body
