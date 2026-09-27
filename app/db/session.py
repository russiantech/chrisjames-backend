# """Async engine, session factory and the FastAPI session dependency."""

# from __future__ import annotations

# from collections.abc import AsyncGenerator
# from contextlib import asynccontextmanager

# from sqlalchemy import event
# from sqlalchemy.engine import Engine
# from sqlalchemy.ext.asyncio import (
#     AsyncEngine,
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )

# from app.core.config import settings

# _is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# engine: AsyncEngine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=settings.DB_ECHO,
#     future=True,
#     pool_pre_ping=not _is_sqlite,
#     # SQLite's async driver does not support the queue pool options below.
#     **({} if _is_sqlite else {"pool_size": 10, "max_overflow": 20, "pool_recycle": 1800}),
# )

# SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
#     bind=engine,
#     class_=AsyncSession,
#     expire_on_commit=False,
#     autoflush=False,
# )


# @event.listens_for(Engine, "connect")
# def _sqlite_pragmas(dbapi_connection, _record) -> None:  # pragma: no cover
#     """Turn on foreign keys and WAL for SQLite, which defaults them off."""
#     if not _is_sqlite:
#         return
#     cursor = dbapi_connection.cursor()
#     try:
#         cursor.execute("PRAGMA foreign_keys=ON")
#         cursor.execute("PRAGMA journal_mode=WAL")
#     finally:
#         cursor.close()


# async def get_db() -> AsyncGenerator[AsyncSession, None]:
#     """Request-scoped session. Commits are explicit in the route handlers."""
#     async with SessionLocal() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise


# @asynccontextmanager
# async def session_scope() -> AsyncGenerator[AsyncSession, None]:
#     """Standalone session for scripts, background tasks and seeding."""
#     async with SessionLocal() as session:
#         try:
#             yield session
#             await session.commit()
#         except Exception:
#             await session.rollback()
#             raise


# async def dispose_engine() -> None:
#     await engine.dispose()




# v2
"""Async engine, session factory and the FastAPI session dependency.

Notes on the Postgres branch:
    The production DATABASE_URL points at Supabase's pgbouncer pooler
    (port 6543, transaction pooling mode). In that mode pgbouncer may hand
    out a *different* underlying Postgres connection for each transaction,
    which breaks asyncpg's default client-side prepared-statement cache
    (symptom: ``DuplicatePreparedStatementError: prepared statement
    "__asyncpg_stmt_1__" already exists``). We disable that cache via
    ``connect_args={"statement_cache_size": 0}``.

    We also use ``NullPool`` for the Postgres branch: pgbouncer is already
    pooling connections for us at the proxy layer, so stacking SQLAlchemy's
    queue pool (``pool_size`` / ``max_overflow``) on top means each of our
    "pooled" connections can still be multiplexed across different backend
    connections by pgbouncer between transactions - the same class of
    mismatch that caused the prepared-statement error. Let pgbouncer own
    pooling; open/close a real connection per checkout on our side.

    If you connect directly to Postgres (port 5432, no pgbouncer) - e.g.
    for migrations - use a separate engine/session without these
    restrictions so you keep the performance benefit of a real pool.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite's async driver does not support the queue pool options or
    # asyncpg-specific connect_args used below.
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        future=True,
        pool_pre_ping=False,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        future=True,
        pool_pre_ping=True,
        # pgbouncer (transaction pooling) already pools connections for us;
        # don't double-pool on top of it.
        poolclass=NullPool,
        # Required for pgbouncer transaction/statement pooling: asyncpg must
        # not cache prepared statements against a connection identity that
        # pgbouncer can silently swap out.
        connect_args={"statement_cache_size": 0},
    )

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:  # pragma: no cover
    """Turn on foreign keys and WAL for SQLite, which defaults them off."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped session. Commits are explicit in the route handlers."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Standalone session for scripts, background tasks and seeding."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()

