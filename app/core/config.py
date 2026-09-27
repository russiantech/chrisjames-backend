"""Application configuration.

All runtime configuration is read from environment variables (or a local
``.env`` file) so the same image can run in development, staging and
production without code changes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
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
    DEBUG: bool = True
    PROJECT_NAME: str = "Christopher James — Portfolio API"
    API_V1_PREFIX: str = "/api/v1"
    SITE_URL: str = "http://localhost:5173"
    OWNER_NAME: str = "Christopher James"
    OWNER_NAME_SHORT: str = "Chris James"
    OWNER_EMAIL: str = "chrisjsmes@gmail.com"

    # ------------------------------------------------------------------- auth
    SECRET_KEY: str = "change-me-in-production-please-use-a-64-char-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFY_EXPIRE_HOURS: int = 48

    # --------------------------------------------------------------- database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'portfolio.db'}"
    DB_ECHO: bool = False

    # ------------------------------------------------------------------- cors
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ------------------------------------------------------------------ email
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_TLS: bool = True
    EMAIL_FROM: str = "Christopher James <no-reply@chrisjames.dev>"
    #: When no SMTP host is configured, e-mails are written to the console and
    #: persisted in the ``email_log`` table instead of being sent.
    EMAIL_DRY_RUN: bool = True

    # ---------------------------------------------------------------- storage
    MEDIA_ROOT: Path = BASE_DIR / "media"
    MEDIA_URL: str = "/media"
    MAX_UPLOAD_MB: int = 64
    ALLOWED_UPLOAD_TYPES: list[str] = [
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
        "video/mp4", "video/webm", "video/quicktime",
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm",
        "application/pdf", "application/zip", "text/plain", "text/markdown",
    ]

    # -------------------------------------------------------------- moderation
    #: When true, posts submitted by users without ``post:publish`` go live
    #: immediately instead of entering the review queue. Overridable at runtime
    #: through the ``site_settings`` table.
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
    #: Credentials for the first superuser, created on startup if absent.
    FIRST_SUPERUSER_EMAIL: str = "admin@chrisjames.dev"
    FIRST_SUPERUSER_PASSWORD: str = "ChangeMe123!"
    FIRST_SUPERUSER_USERNAME: str = "chrisjames"

    # ------------------------------------------------------------ rate limits
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_ANON_PER_MINUTE: int = 90
    RATE_LIMIT_AUTH_PER_MINUTE: int = 300

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def docs_url(self) -> str | None:
        return None if self.is_production else "/docs"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()

__all__ = ["Settings", "settings", "get_settings", "BASE_DIR", "AnyHttpUrl", "Field"]
