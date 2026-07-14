import redis.asyncio as redis

from app.config import get_settings


async def ping_redis() -> bool:
    client = redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
