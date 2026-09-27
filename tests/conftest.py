"""Test fixtures: a fresh database and an HTTP client per test session."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("EMAIL_DRY_RUN", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import httpx
from asgi_lifespan import LifespanManager  # type: ignore


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def client():
    Path("./test.db").unlink(missing_ok=True)
    from app.main import app

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as http_client:
            yield http_client
    Path("./test.db").unlink(missing_ok=True)


@pytest_asyncio.fixture(scope="session")
async def owner_token(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin@chrisjames.dev", "password": "ChangeMe123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth(owner_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {owner_token}"}
