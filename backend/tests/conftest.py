import asyncio
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app

if sys.platform == "win32":
    # psycopg (used by the LangGraph Postgres checkpointer) refuses to run
    # async on Windows' default ProactorEventLoop and requires SelectorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
