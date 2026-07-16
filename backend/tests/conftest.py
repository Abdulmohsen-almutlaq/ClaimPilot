import asyncio
import os
import sys

# CI runs with APP_ENV=test (NullPool engine); local .env says dev, whose pooled
# connections break across pytest event loops. Must be set before app imports.
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient

from app.db.seed import seed_policies, seed_users
from app.main import app

if sys.platform == "win32":
    # psycopg (used by the LangGraph Postgres checkpointer) refuses to run
    # async on Windows' default ProactorEventLoop and requires SelectorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def _seed_demo_data() -> None:
    """Auth is DB-backed (demo users) and validate looks policies up in the DB,
    so both are seeded once per session. Tolerates an unreachable database:
    pure unit tests still run without Postgres, and DB-dependent tests fail on
    their own with clearer errors."""
    try:
        asyncio.run(seed_users())
        asyncio.run(seed_policies())
    except Exception:
        pass


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
