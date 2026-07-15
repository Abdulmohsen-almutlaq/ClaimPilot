import datetime
import json
from collections.abc import Awaitable
from typing import Any, cast

import redis.asyncio as redis

from app.config import get_settings

DLQ_KEY = "claimpilot:dlq"


def _client() -> redis.Redis:
    client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
        get_settings().redis_url
    )
    return client


async def push_dlq(*, case_id: str, error: str, traceback_text: str) -> None:
    entry = json.dumps(
        {
            "case_id": case_id,
            "error": error,
            "traceback": traceback_text,
            "failed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    )
    client = _client()
    try:
        # redis-py ships one signature for sync and async clients, so list ops
        # are typed as `Awaitable[T] | T` — cast to the async side.
        await cast(Awaitable[int], client.rpush(DLQ_KEY, entry))
    finally:
        await client.aclose()


async def list_dlq() -> list[dict[str, Any]]:
    client = _client()
    try:
        raw_entries = await cast(Awaitable[list[bytes]], client.lrange(DLQ_KEY, 0, -1))
    finally:
        await client.aclose()
    return [json.loads(raw) for raw in raw_entries]


async def pop_dlq_entry(case_id: str) -> dict[str, Any] | None:
    """Remove and return the DLQ entry for a case (None if absent). Removal
    happens before requeueing so a crash between the two leaves the case
    requeued-or-still-dead, never duplicated."""
    client = _client()
    try:
        raw_entries = await cast(Awaitable[list[bytes]], client.lrange(DLQ_KEY, 0, -1))
        for raw in raw_entries:
            entry = json.loads(raw)
            if entry.get("case_id") == case_id:
                await cast(Awaitable[int], client.lrem(DLQ_KEY, 1, raw.decode()))
                return dict(entry)
    finally:
        await client.aclose()
    return None


async def dlq_depth() -> int:
    client = _client()
    try:
        return int(await cast(Awaitable[int], client.llen(DLQ_KEY)))
    finally:
        await client.aclose()
