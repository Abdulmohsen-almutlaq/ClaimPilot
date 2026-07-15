from typing import Any

import httpx

from app.config import get_settings
from app.tools.circuit_breaker import CircuitBreaker


class CRMError(Exception):
    pass


class CRMNotFoundError(CRMError):
    pass


class CRMUnavailableError(CRMError):
    pass


# One breaker per worker process is the right scope: it exists to stop THIS
# process from hammering a dead dependency, not to coordinate globally.
_breaker: CircuitBreaker | None = None


def get_breaker() -> CircuitBreaker:
    global _breaker
    if _breaker is None:
        settings = get_settings()
        _breaker = CircuitBreaker(
            failure_threshold=settings.crm_breaker_failure_threshold,
            open_seconds=settings.crm_breaker_open_seconds,
        )
    return _breaker


def reset_breaker() -> None:
    """Test seam: breakers hold state across calls by design, which tests must
    be able to reset between cases."""
    global _breaker
    _breaker = None


async def _get(path: str, *, timeout: float | None) -> dict[str, Any]:
    breaker = get_breaker()
    breaker.check()  # raises CircuitOpenError without attempting the call

    settings = get_settings()
    url = f"{settings.crm_base_url}{path}"
    effective_timeout = timeout if timeout is not None else settings.crm_timeout_seconds
    try:
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        breaker.record_failure()
        raise CRMUnavailableError(str(exc)) from exc

    if resp.status_code >= 500:
        breaker.record_failure()
        raise CRMUnavailableError(f"CRM returned {resp.status_code} for {path}")
    # 404 means the service answered — that's a healthy dependency.
    breaker.record_success()
    if resp.status_code == 404:
        raise CRMNotFoundError(f"{path} not found")
    resp.raise_for_status()
    result: dict[str, Any] = resp.json()
    return result


async def lookup_policy(policy_number: str, *, timeout: float | None = None) -> dict[str, Any]:
    return await _get(f"/policies/{policy_number}", timeout=timeout)


async def get_customer(customer_id: str, *, timeout: float | None = None) -> dict[str, Any]:
    return await _get(f"/customers/{customer_id}", timeout=timeout)
