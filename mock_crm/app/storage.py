from typing import Any, Protocol

import asyncpg

from app.seed_data import CUSTOMERS, POLICIES


class Store(Protocol):
    async def get_policy(self, policy_number: str) -> dict[str, Any] | None: ...

    async def get_customer(self, customer_id: str) -> dict[str, Any] | None: ...


class InMemoryStore:
    """Test backend: seed data straight from memory, no external dependency, so
    the service's own CI job needs no database."""

    async def get_policy(self, policy_number: str) -> dict[str, Any] | None:
        return dict(POLICIES[policy_number]) if policy_number in POLICIES else None

    async def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        return dict(CUSTOMERS[customer_id]) if customer_id in CUSTOMERS else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policies (
    policy_number TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    status TEXT NOT NULL,
    category TEXT NOT NULL,
    coverage_limit DOUBLE PRECISION NOT NULL,
    effective_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL
);
"""


class PostgresStore:
    """Runtime backend: the dedicated crm_postgres container (docker-compose).
    Self-initializing — creates its schema and upserts seed data on startup so
    `docker compose up` stays zero-step."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)
            for customer in CUSTOMERS.values():
                await conn.execute(
                    "INSERT INTO customers (customer_id, name, email) VALUES ($1, $2, $3) "
                    "ON CONFLICT (customer_id) DO UPDATE SET name = $2, email = $3",
                    customer["customer_id"],
                    customer["name"],
                    customer["email"],
                )
            for policy in POLICIES.values():
                await conn.execute(
                    "INSERT INTO policies (policy_number, customer_id, status, category, "
                    "coverage_limit, effective_date, expiry_date) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                    "ON CONFLICT (policy_number) DO UPDATE SET customer_id = $2, status = $3, "
                    "category = $4, coverage_limit = $5, effective_date = $6, expiry_date = $7",
                    policy["policy_number"],
                    policy["customer_id"],
                    policy["status"],
                    policy["category"],
                    policy["coverage_limit"],
                    policy["effective_date"],
                    policy["expiry_date"],
                )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresStore.connect() was never called")
        return self._pool

    async def get_policy(self, policy_number: str) -> dict[str, Any] | None:
        row = await self._require_pool().fetchrow(
            "SELECT * FROM policies WHERE policy_number = $1", policy_number
        )
        return dict(row) if row is not None else None

    async def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        row = await self._require_pool().fetchrow(
            "SELECT * FROM customers WHERE customer_id = $1", customer_id
        )
        return dict(row) if row is not None else None
