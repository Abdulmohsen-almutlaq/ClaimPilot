from typing import Any

import httpx

from app.config import get_settings


class CRMError(Exception):
    pass


class CRMNotFoundError(CRMError):
    pass


class CRMUnavailableError(CRMError):
    pass


async def _get(path: str, *, timeout: float | None) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.crm_base_url}{path}"
    effective_timeout = timeout if timeout is not None else settings.crm_timeout_seconds
    try:
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        raise CRMUnavailableError(str(exc)) from exc

    if resp.status_code == 404:
        raise CRMNotFoundError(f"{path} not found")
    if resp.status_code >= 500:
        raise CRMUnavailableError(f"CRM returned {resp.status_code} for {path}")
    resp.raise_for_status()
    result: dict[str, Any] = resp.json()
    return result


async def lookup_policy(policy_number: str, *, timeout: float | None = None) -> dict[str, Any]:
    return await _get(f"/policies/{policy_number}", timeout=timeout)


async def get_customer(customer_id: str, *, timeout: float | None = None) -> dict[str, Any]:
    return await _get(f"/customers/{customer_id}", timeout=timeout)
