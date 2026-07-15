import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.storage import InMemoryStore, PostgresStore, Store


class Policy(BaseModel):
    policy_number: str
    customer_id: str
    status: str
    category: str
    coverage_limit: float
    effective_date: str
    expiry_date: str


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str


def _build_store() -> Store:
    # CRM_DATABASE_URL set (docker-compose) -> real Postgres; unset (tests,
    # bare local runs) -> in-memory seed data. Same Store interface either way.
    dsn = os.environ.get("CRM_DATABASE_URL")
    return PostgresStore(dsn) if dsn else InMemoryStore()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = app.state.store
    if isinstance(store, PostgresStore):
        await store.connect()
    yield
    if isinstance(store, PostgresStore):
        await store.close()


def _chaos_mode() -> str:
    return os.environ.get("CHAOS_MODE", "").lower()


async def _apply_chaos() -> None:
    mode = _chaos_mode()
    if mode == "down":
        raise HTTPException(status_code=503, detail="CRM unavailable")
    if mode == "latency":
        await asyncio.sleep(3)
    elif mode == "errors":
        raise HTTPException(status_code=500, detail="Simulated CRM error")


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="Mock CRM", lifespan=_lifespan)
    app.state.store = store if store is not None else _build_store()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "chaos_mode": _chaos_mode() or "none"}

    @app.get("/policies/{policy_number}", response_model=Policy)
    async def get_policy(policy_number: str, request: Request) -> Policy:
        await _apply_chaos()
        policy = await request.app.state.store.get_policy(policy_number)
        if policy is None:
            raise HTTPException(status_code=404, detail="Policy not found")
        return Policy(**policy)

    @app.get("/customers/{customer_id}", response_model=Customer)
    async def get_customer(customer_id: str, request: Request) -> Customer:
        await _apply_chaos()
        customer = await request.app.state.store.get_customer(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return Customer(**customer)

    return app


app = create_app()
