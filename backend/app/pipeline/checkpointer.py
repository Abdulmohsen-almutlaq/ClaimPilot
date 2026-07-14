from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import get_settings


def _psycopg_dsn(database_url: str) -> str:
    # SQLAlchemy's asyncpg driver URL isn't a psycopg-compatible DSN; the
    # checkpointer talks to Postgres directly via psycopg, not through our ORM.
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    dsn = _psycopg_dsn(get_settings().database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        yield saver


async def setup_checkpointer_tables() -> None:
    dsn = _psycopg_dsn(get_settings().database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
