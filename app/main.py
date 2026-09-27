"""Application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import dispose_engine

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("portfolio")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.init_db import initialise

    await initialise()
    logger.info("API ready — %s (%s)", settings.PROJECT_NAME, settings.ENVIRONMENT)
    yield
    await dispose_engine()


DESCRIPTION = """
The API behind **christopherjames.dev** — portfolio, blog and back office.

* **Blog** — posts built from ordered content blocks: rich text, markdown,
  highlighted code, images, galleries, video, audio, embeds, tables, polls and
  inline advert slots.
* **Contributions** — team members and signed-out visitors can submit posts.
  Submissions enter a review queue, or publish straight away when the
  auto-publish switch is on.
* **Conversation** — threaded comments with replies, reactions, mentions,
  reports and a moderation queue.
* **Notifications** — in-app, e-mail and webhook, with per-kind preferences and
  a live server-sent event stream.
* **Commerce** — plans, checkout, webhooks and refunds; advert slots with
  scheduling, targeting, caps and click tracking.
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=DESCRIPTION,
        version="1.0.0",
        docs_url=settings.docs_url,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
        contact={"name": settings.OWNER_NAME, "email": settings.OWNER_EMAIL},
    )

    app.add_middleware(SecurityHeadersMiddleware)
    if settings.RATE_LIMIT_ENABLED:
        app.add_middleware(
            RateLimitMiddleware,
            anon_per_minute=settings.RATE_LIMIT_ANON_PER_MINUTE,
            auth_per_minute=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.mount(
        settings.MEDIA_URL,
        StaticFiles(directory=settings.MEDIA_ROOT),
        name="media",
    )

    # ---------------------------------------------------------- error shape
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "detail": exc.detail,
                "details": getattr(exc, "details", None),
                "request_id": getattr(request.state, "request_id", None),
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in error["loc"][1:]) or "body",
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_failed",
                "detail": "Some fields need fixing.",
                "details": fields,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Integrity error: %s", exc)
        return JSONResponse(
            status_code=409,
            content={
                "code": "conflict",
                "detail": "That conflicts with something that already exists.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "code": "server_error",
                "detail": "Something broke on our side. The error has been logged.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.ENVIRONMENT, "version": "1.0.0"}

    return app


app = create_app()
