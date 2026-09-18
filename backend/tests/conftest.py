import os

import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://theshed:theshed@localhost:5432/theshed"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """A real Postgres session against the local dev database, wrapped in a
    transaction that's rolled back after the test — not mocked. Per the
    testing discipline in docs/architecture.md, LLM calls are what get
    mocked; a real local database is a legitimate, standard thing to test
    against directly.

    `join_transaction_mode="create_savepoint"` matters here: several
    service functions under test (stream_turn, verify_turn) call
    `session.commit()` themselves. Without this, that commit would end the
    outer transaction early, and the `connection.rollback()` below would
    have nothing left to undo — silently leaking test data into the real
    dev database. This makes the session's own commits into savepoint
    releases instead, so the outer rollback still discards everything."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> Redis:
    """Real local Redis, on a separate DB index (15) reserved for tests, so
    a test run never touches dev-mode session data. Flushed after each
    test."""
    client = Redis.from_url(TEST_REDIS_URL)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
