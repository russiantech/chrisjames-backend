"""Request id, timing, a small rate limiter and security headers."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Tag every request with an id and report how long it took."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window limiter, per client, in memory.

    Good enough for a single-instance deployment. Behind several workers, move
    the counter to Redis — the interface stays the same.
    """

    def __init__(self, app, anon_per_minute: int, auth_per_minute: int) -> None:
        super().__init__(app)
        self.anon_limit = anon_per_minute
        self.auth_limit = auth_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _identity(self, request: Request) -> tuple[str, int]:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            return authorization[-32:], self.auth_limit
        forwarded = request.headers.get("x-forwarded-for")
        ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else "unknown")
        )
        return ip, self.anon_limit

    async def dispatch(self, request: Request, call_next):
        # The SSE stream is one long connection, not a burst of requests.
        if request.url.path.endswith("/notifications/stream"):
            return await call_next(request)

        key, limit = self._identity(request)
        now = time.time()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()

        if len(window) >= limit:
            retry_after = int(60 - (now - window[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limited",
                    "detail": "Too many requests. Wait a moment and try again.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(window)))
        return response
