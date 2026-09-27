# """Application configuration.

# All runtime configuration is read from environment variables (or a local
# ``.env`` file) so the same image can run in development, staging and
# production without code changes.
# """

# from __future__ import annotations

# from functools import lru_cache
# from pathlib import Path
# from typing import Literal

# from pydantic import AnyHttpUrl, Field, field_validator
# from pydantic_settings import BaseSettings, SettingsConfigDict

# BASE_DIR = Path(__file__).resolve().parents[2]


# class Settings(BaseSettings):
#     model_config = SettingsConfigDict(
#         env_file=(BASE_DIR / ".env"),
#         env_file_encoding="utf-8",
#         case_sensitive=False,
#         extra="ignore",
#     )

#     # ---------------------------------------------------------------- general
#     ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
#     DEBUG: bool = True
#     PROJECT_NAME: str = "Christopher James — Portfolio API"
#     API_V1_PREFIX: str = "/api/v1"
#     SITE_URL: str = "http://localhost:5173"
#     OWNER_NAME: str = "Christopher James"
#     OWNER_NAME_SHORT: str = "Chris James"
#     OWNER_EMAIL: str = "chrisjsmes@gmail.com"

#     # ------------------------------------------------------------------- auth
#     SECRET_KEY: str = "VIu29wn3r7g8f9s0d1f2g3h4j5k6l7m8n9o0p1q2r3s4t5u6v7w8x9y0z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p1q2r3s4t5u6v7w8x9y0z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p1q2r3s4t5u6v7w8x9y0z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p1q2r3s4t5u6v7w8x9y0z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p1q2r3s4t5u6v7w8x9y0z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q"
#     JWT_ALGORITHM: str = "HS256"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
#     REFRESH_TOKEN_EXPIRE_DAYS: int = 30
#     PASSWORD_RESET_EXPIRE_MINUTES: int = 60
#     EMAIL_VERIFY_EXPIRE_HOURS: int = 48

#     # --------------------------------------------------------------- database
#     DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'portfolio.db'}"
#     DB_ECHO: bool = False

#     # ------------------------------------------------------------------- cors
#     CORS_ORIGINS: list[str] = [
#         "http://localhost:5173",
#         "http://127.0.0.1:5173",
#         "http://localhost:4173",
#     ]

#     @field_validator("CORS_ORIGINS", mode="before")
#     @classmethod
#     def _split_origins(cls, value: object) -> object:
#         if isinstance(value, str):
#             return [origin.strip() for origin in value.split(",") if origin.strip()]
#         return value

#     # ------------------------------------------------------------------ email
#     SMTP_HOST: str | None = None
#     SMTP_PORT: int = 587
#     SMTP_USER: str | None = None
#     SMTP_PASSWORD: str | None = None
#     SMTP_TLS: bool = True
#     EMAIL_FROM: str = "Christopher James <no-reply@chrisjames.dev>"
#     #: When no SMTP host is configured, e-mails are written to the console and
#     #: persisted in the ``email_log`` table instead of being sent.
#     EMAIL_DRY_RUN: bool = True

#     # ---------------------------------------------------------------- storage
#     MEDIA_ROOT: Path = BASE_DIR / "media"
#     MEDIA_URL: str = "/media"
#     MAX_UPLOAD_MB: int = 64
#     ALLOWED_UPLOAD_TYPES: list[str] = [
#         "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
#         "video/mp4", "video/webm", "video/quicktime",
#         "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm",
#         "application/pdf", "application/zip", "text/plain", "text/markdown",
#     ]

#     # -------------------------------------------------------------- moderation
#     #: When true, posts submitted by users without ``post:publish`` go live
#     #: immediately instead of entering the review queue. Overridable at runtime
#     #: through the ``site_settings`` table.
#     AUTO_PUBLISH_SUBMISSIONS: bool = False
#     AUTO_APPROVE_COMMENTS: bool = True
#     COMMENTS_REQUIRE_LOGIN: bool = False

#     # ---------------------------------------------------------------- payments
#     PAYMENT_PROVIDER: Literal["stripe", "paystack", "flutterwave", "mock"] = "mock"
#     STRIPE_SECRET_KEY: str | None = None
#     STRIPE_WEBHOOK_SECRET: str | None = None
#     PAYSTACK_SECRET_KEY: str | None = None
#     PAYSTACK_WEBHOOK_SECRET: str | None = None
#     FLUTTERWAVE_SECRET_KEY: str | None = None
#     FLUTTERWAVE_WEBHOOK_SECRET: str | None = None
#     DEFAULT_CURRENCY: str = "USD"

#     # --------------------------------------------------------------- bootstrap
#     #: Credentials for the first superuser, created on startup if absent.
#     FIRST_SUPERUSER_EMAIL: str = "admin@chrisjames.dev"
#     FIRST_SUPERUSER_PASSWORD: str = "ChangeMe123!"
#     FIRST_SUPERUSER_USERNAME: str = "chrisjames"

#     # ------------------------------------------------------------ rate limits
#     RATE_LIMIT_ENABLED: bool = True
#     RATE_LIMIT_ANON_PER_MINUTE: int = 90
#     RATE_LIMIT_AUTH_PER_MINUTE: int = 300

#     @property
#     def is_production(self) -> bool:
#         return self.ENVIRONMENT == "production"

#     @property
#     def docs_url(self) -> str | None:
#         return None if self.is_production else "/docs"


# @lru_cache
# def get_settings() -> Settings:
#     settings = Settings()
#     settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
#     return settings


# settings = get_settings()

# __all__ = ["Settings", "settings", "get_settings", "BASE_DIR", "AnyHttpUrl", "Field"]



# v2
"""Application configuration.

Every value can be overridden by an environment variable (or a local
``.env`` file). Secrets have NO defaults — the app refuses to boot in
production if they are missing, and dev-only fallbacks never apply there.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------- general
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False                      # opt IN via env, never default on
    PROJECT_NAME: str = "Christopher James — Portfolio API"
    API_V1_PREFIX: str = "/api/v1"
    SITE_URL: str = "http://localhost:5173"
    OWNER_NAME: str = "Christopher James"
    OWNER_NAME_SHORT: str = "Chris James"
    OWNER_EMAIL: str = "chrisjsmes@gmail.com"

    # ------------------------------------------------------------------- auth
    # No default. Must come from .env (dev) or the platform's env vars (prod).
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFY_EXPIRE_HOURS: int = 48

    # --------------------------------------------------------------- database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'portfolio.db'}"
    DB_ECHO: bool = False

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _force_asyncpg(cls, value: object) -> object:
        """Accept plain `postgresql://` URLs and coerce them to asyncpg.

        SQLAlchemy 2.0 defaults `postgresql://` to psycopg (v3), which we
        don't ship. Normalizing here means session.py, Alembic and tests all
        agree on the driver regardless of what the env var literally says.
        """
        if isinstance(value, str):
            if value.startswith("postgresql+psycopg"):
                return value.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # ------------------------------------------------------------------- cors
    # Comma-separated string in env: CORS_ORIGINS="https://a.com,https://b.com"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    # ------------------------------------------------------------------ email
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_TLS: bool = True
    EMAIL_FROM: str = "Christopher James <no-reply@chrisjames.dev>"
    EMAIL_DRY_RUN: bool = True

    # ---------------------------------------------------------------- storage
    # Vercel/serverless filesystems are read-only except /tmp. Override
    # MEDIA_ROOT to an object-storage mount or /tmp for ephemeral deploys.
    MEDIA_ROOT: Path = Field(
        default_factory=lambda: Path("/tmp/media")
        if _is_serverless()
        else BASE_DIR / "media",
    )
    MEDIA_URL: str = "/media"
    MAX_UPLOAD_MB: int = 64
    ALLOWED_UPLOAD_TYPES: list[str] = [
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
        "video/mp4", "video/webm", "video/quicktime",
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm",
        "application/pdf", "application/zip", "text/plain", "text/markdown",
    ]

    # -------------------------------------------------------------- moderation
    AUTO_PUBLISH_SUBMISSIONS: bool = False
    AUTO_APPROVE_COMMENTS: bool = True
    COMMENTS_REQUIRE_LOGIN: bool = False

    # ---------------------------------------------------------------- payments
    PAYMENT_PROVIDER: Literal["stripe", "paystack", "flutterwave", "mock"] = "mock"
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    PAYSTACK_SECRET_KEY: str | None = None
    PAYSTACK_WEBHOOK_SECRET: str | None = None
    FLUTTERWAVE_SECRET_KEY: str | None = None
    FLUTTERWAVE_WEBHOOK_SECRET: str | None = None
    DEFAULT_CURRENCY: str = "USD"

    # --------------------------------------------------------------- bootstrap
    FIRST_SUPERUSER_EMAIL: str = "admin@chrisjames.dev"
    FIRST_SUPERUSER_USERNAME: str = "chrisjames"
    # No default password — must be supplied or the app refuses to boot.
    FIRST_SUPERUSER_PASSWORD: str

    # ------------------------------------------------------------ rate limits
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_ANON_PER_MINUTE: int = 90
    RATE_LIMIT_AUTH_PER_MINUTE: int = 300

    # ------------------------------------------------------------- validation
    @model_validator(mode="after")
    def _production_sanity(self) -> "Settings":
        """Fail fast rather than boot misconfigured."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if self.EMAIL_DRY_RUN:
                raise ValueError("EMAIL_DRY_RUN must be false in production")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("DATABASE_URL must be PostgreSQL in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def docs_url(self) -> str | None:
        return None if self.is_production else "/docs"


def _is_serverless() -> bool:
    """Heuristic: AWS Lambda / Vercel set AWS_LAMBDA_FUNCTION_NAME or VERCEL."""
    import os
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("VERCEL"))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()

__all__ = ["Settings", "settings", "get_settings", "BASE_DIR"]

