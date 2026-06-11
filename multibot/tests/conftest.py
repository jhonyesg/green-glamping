import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings

settings = get_settings()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
def redis_client():
    import redis
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield client
    client.close()


@pytest.fixture
def tenant_factory():
    """Return a factory function that builds tenant-like dicts for testing."""
    def _make(slug: str = "test", mode: str = "hybrid", **kwargs):
        return {
            "slug": slug,
            "name": kwargs.get("name", f"Tenant {slug}"),
            "operation_mode": mode,
            **kwargs,
        }
    return _make
