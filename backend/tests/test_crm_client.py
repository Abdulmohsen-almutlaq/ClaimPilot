import httpx
import pytest
import respx

from app.tools import crm

CRM_BASE = "http://localhost:8001"


async def test_lookup_policy_success() -> None:
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(
            return_value=httpx.Response(
                200, json={"policy_number": "POL-AUTO-001", "status": "active"}
            )
        )
        result = await crm.lookup_policy("POL-AUTO-001")
    assert result["status"] == "active"


async def test_lookup_policy_not_found() -> None:
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/unknown").mock(return_value=httpx.Response(404))
        with pytest.raises(crm.CRMNotFoundError):
            await crm.lookup_policy("unknown")


async def test_lookup_policy_server_error() -> None:
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(return_value=httpx.Response(500))
        with pytest.raises(crm.CRMUnavailableError):
            await crm.lookup_policy("POL-AUTO-001")


async def test_lookup_policy_connection_error() -> None:
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(crm.CRMUnavailableError):
            await crm.lookup_policy("POL-AUTO-001")


async def test_get_customer_success() -> None:
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/customers/cust-1001").mock(
            return_value=httpx.Response(
                200, json={"customer_id": "cust-1001", "name": "Ava Thompson"}
            )
        )
        result = await crm.get_customer("cust-1001")
    assert result["name"] == "Ava Thompson"
