"""The v1 router: every endpoint hangs off this one object."""

from fastapi import APIRouter

from app.api.v1.routers import (
    adverts,
    auth,
    comments,
    inbox,
    # mediav2 as media,
    media,
    notifications,
    payments,
    polls,
    portfolio,
    posts,
    site,
    taxonomy,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(posts.router)
api_router.include_router(comments.router)
api_router.include_router(polls.router)
api_router.include_router(taxonomy.router)
api_router.include_router(media.router)
api_router.include_router(notifications.router)
api_router.include_router(inbox.router)
api_router.include_router(payments.router)
api_router.include_router(adverts.router)
api_router.include_router(portfolio.router)
api_router.include_router(site.router)
