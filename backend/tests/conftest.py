"""单元/集成测试基础:用 SQLite in-memory + aiosqlite,避免依赖 docker。
生产/集成测试再改 testcontainers。"""

import os
import uuid

os.environ.setdefault("APP_ENCRYPTION_KEY", "zmWkQ4E3S1m-_7fCxVU2hVJ0b4N8tGxkgD6bYvTqP4Y=")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "True")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def engine():
    from app.core.database import Base
    import app.models  # noqa: F401

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_maker):
    async with session_maker() as s:
        yield s


@pytest_asyncio.fixture
async def client(session_maker):
    from app.api.v1 import deps
    from app.main import app

    async def override_session():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[deps.get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def user_headers() -> dict:
    return {
        "X-User-Id": f"github:{uuid.uuid4()}",
        "X-User-Email": "test@example.com",
        "X-User-Name": "Test User",
    }
