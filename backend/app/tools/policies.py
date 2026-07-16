from typing import Any

from sqlalchemy import select

from app.db.session import session_factory
from app.models.policy import Policy


async def lookup_policy(policy_number: str) -> dict[str, Any] | None:
    """Policy lookup against the app database. The CRM data lives in the main
    Postgres (no HTTP hop, so no timeout/circuit-breaker machinery); None means
    the policy does not exist."""
    async with session_factory() as session:
        policy = await session.scalar(
            select(Policy).where(Policy.policy_number == policy_number)
        )
    if policy is None:
        return None
    return {
        "policy_number": policy.policy_number,
        "customer_id": policy.customer_id,
        "customer_name": policy.customer_name,
        "status": policy.status,
        "category": policy.category,
        "coverage_limit": float(policy.coverage_limit),
        "effective_date": policy.effective_date,
        "expiry_date": policy.expiry_date,
    }
