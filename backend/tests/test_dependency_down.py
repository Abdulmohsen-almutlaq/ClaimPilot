"""Chaos behavior (spec 5.2 / acceptance criteria): CRM down means cases route
to a human with reason dependency_down — never needs_info (we don't ask the
customer to fix OUR outage), never a crash."""

import httpx
import respx
from fakes import FakeRetriever, SchemaAwareAdapter

from app.llm.client import LLMClient
from app.pipeline.graph import compile_graph
from app.pipeline.nodes.validate import run_validate
from app.pipeline.state import CaseState

CRM_BASE = "http://localhost:8001"

_FIELDS = {
    "claimant_name": "Jane Doe",
    "policy_number": "POL-AUTO-001",
    "incident_date": "2026-01-05",
    "claimed_amount": "1200.00",
    "category": "auto",
    "description": "Rear-end collision",
}


async def test_crm_5xx_routes_to_human_not_needs_info() -> None:
    state: CaseState = {"extracted_fields": _FIELDS}
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(return_value=httpx.Response(503))
        update = await run_validate(state)

    assert update["status"] == "human_queue"
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "dependency_down"


async def test_crm_connection_error_routes_to_human() -> None:
    state: CaseState = {"extracted_fields": _FIELDS}
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(side_effect=httpx.ConnectError("refused"))
        update = await run_validate(state)

    assert update["route_reason"] == "dependency_down"


async def test_full_graph_survives_crm_down_without_crashing() -> None:
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)
    graph = compile_graph(llm_client, FakeRetriever(), None)

    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(return_value=httpx.Response(503))
        final = await graph.ainvoke({"document_text": "some claim text"})

    assert final["status"] == "human_queue"
    assert final["route"] == "human_queue"
    assert final["route_reason"] == "dependency_down"
    # pipeline stopped cleanly after validate: no draft/qa tokens were burned
    assert SchemaAwareAdapter.calls == ["ClaimFields"]


async def test_open_breaker_short_circuits_subsequent_cases() -> None:
    from app.tools import crm

    crm.reset_breaker()
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)
    graph = compile_graph(llm_client, FakeRetriever(), None)

    with respx.mock(base_url=CRM_BASE) as mock:
        route = mock.get("/policies/POL-AUTO-001").mock(return_value=httpx.Response(503))
        # three cases fail against the dead CRM -> breaker opens
        for _ in range(3):
            await graph.ainvoke({"document_text": "some claim text"})
        assert route.call_count == 3

        # the fourth case routes to a human instantly, zero HTTP calls
        final = await graph.ainvoke({"document_text": "some claim text"})
        assert final["route_reason"] == "dependency_down"
        assert route.call_count == 3
