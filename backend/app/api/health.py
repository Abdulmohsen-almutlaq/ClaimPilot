from fastapi import APIRouter
from pydantic import BaseModel

from app.core.redis import ping_redis
from app.db.session import ping_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    dependencies: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = await ping_db()
    redis_ok = await ping_redis()
    dependencies = {
        "db": "ok" if db_ok else "down",
        "redis": "ok" if redis_ok else "down",
        "llm": "not_configured",
        "crm": "not_configured",
    }
    overall = "ok" if db_ok and redis_ok else "degraded"
    return HealthResponse(status=overall, dependencies=dependencies)
