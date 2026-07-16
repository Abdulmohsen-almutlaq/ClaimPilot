import asyncio
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from app.auth.security import hash_password
from app.db.session import session_factory
from app.models.policy import Policy
from app.models.user import User

_DEMO_USERS = [
    ("submitter@demo.io", "demo", "submitter"),
    ("approver@demo.io", "demo", "approver"),
    ("admin@demo.io", "demo", "admin"),
]

# Formerly the mock CRM's seed data (its service and separate Postgres were
# removed); the pipeline validates claims against these rows directly.
_POLICIES: list[dict[str, Any]] = [
    {
        "policy_number": "POL-AUTO-001",
        "customer_id": "cust-1001",
        "customer_name": "Ava Thompson",
        "status": "active",
        "category": "auto",
        "coverage_limit": 25000,
        "effective_date": "2025-01-01",
        "expiry_date": "2026-12-31",
    },
    {
        "policy_number": "POL-HOME-002",
        "customer_id": "cust-1002",
        "customer_name": "Marcus Lee",
        "status": "active",
        "category": "home",
        "coverage_limit": 150000,
        "effective_date": "2024-06-01",
        "expiry_date": "2026-06-01",
    },
    # POL-HEALTH-003 stays lapsed on purpose — it powers invalid-policy cases.
    {
        "policy_number": "POL-HEALTH-003",
        "customer_id": "cust-1003",
        "customer_name": "Priya Nair",
        "status": "lapsed",
        "category": "health",
        "coverage_limit": 50000,
        "effective_date": "2023-01-01",
        "expiry_date": "2024-01-01",
    },
    {
        "policy_number": "POL-HEALTH-004",
        "customer_id": "cust-1003",
        "customer_name": "Priya Nair",
        "status": "active",
        "category": "health",
        "coverage_limit": 50000,
        "effective_date": "2025-06-01",
        "expiry_date": "2027-06-01",
    },
]


async def seed_users() -> None:
    async with session_factory() as session:
        for email, password, role in _DEMO_USERS:
            stmt = (
                insert(User)
                .values(email=email, password_hash=hash_password(password), role=role)
                .on_conflict_do_nothing(index_elements=["email"])
            )
            await session.execute(stmt)
        await session.commit()


async def seed_policies() -> None:
    async with session_factory() as session:
        for policy in _POLICIES:
            stmt = (
                insert(Policy)
                .values(**policy)
                .on_conflict_do_nothing(index_elements=["policy_number"])
            )
            await session.execute(stmt)
        await session.commit()


async def seed_all() -> None:
    # One event loop for both: the dev engine pools connections, and a second
    # asyncio.run() would reuse connections bound to the first (closed) loop.
    await seed_users()
    await seed_policies()


def main() -> None:
    asyncio.run(seed_all())


if __name__ == "__main__":
    main()
