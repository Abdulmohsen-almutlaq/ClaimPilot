from typing import Any

import httpx

from app.config import get_settings


class CRMError(Exception):
    pass


class CRMNotFoundError(CRMError):
    pass


class CRMUnavailableError(CRMError):
    pass


async def _get(path: str, *, timeout: float) -> dict[str, Any]:
    url = f"{get_settings().crm_base_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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


async def lookup_policy(policy_number: str, *, timeout: float = 5.0) -> dict[str, Any]:
    return await _get(f"/policies/{policy_number}", timeout=timeout)


async def get_customer(customer_id: str, *, timeout: float = 5.0) -> dict[str, Any]:
    return await _get(f"/customers/{customer_id}", timeout=timeout)
