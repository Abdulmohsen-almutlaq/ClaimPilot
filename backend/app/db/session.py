from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

_settings = get_settings()
_engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if _settings.app_env == "test":
    # Test runs mix pytest-asyncio's loop with TestClient's own internal loop;
    # a pooled connection can outlive the loop it was created on. NullPool opens
    # a fresh connection per checkout, sidestepping that class of error entirely.
    _engine_kwargs = {"poolclass": NullPool}

engine = create_async_engine(_settings.database_url, **_engine_kwargs)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def ping_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
