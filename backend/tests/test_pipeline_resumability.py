import uuid

import httpx
import pytest
import respx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from app.llm.adapters import TokenUsage
from app.llm.client import LLMClient
from app.pipeline.checkpointer import get_checkpointer, setup_checkpointer_tables
from app.pipeline.graph import compile_graph
from app.pipeline.schemas import Evidence
from app.pipeline.state import CaseState

CRM_BASE = "http://localhost:8001"


class _FakeRetriever:
    async def retrieve(self, query: str, *, category: str | None = None) -> list[Evidence]:
        return [
            Evidence(
                clause_id="AUTO-001",
                text="Collision coverage up to $25,000.",
                similarity=0.9,
            )
        ]


class _TrackingAdapter:
    """Fake adapter shared by both the intake and draft nodes in this test —
    it shapes its response by schema name and records every call so the test
    can assert intake specifically never re-ran, not just that draft succeeded.
    """

    calls: list[str] = []

    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        _TrackingAdapter.calls.append(schema.__name__)
        data: BaseModel
        if schema.__name__ == "ClaimFields":
            data = schema(
                claimant_name="Jane Doe",
                policy_number="POL-AUTO-001",
                incident_date="2026-01-05",
                claimed_amount="1200.00",
                category="auto",
                description="Rear-end collision",
            )
        else:
            data = schema(
                decision="approve",
                payout_amount="1200.00",
                reasoning="Validation passed.",
                citations=[],
                confidence=0.9,
            )
        return data, TokenUsage(input_tokens=10, output_tokens=5)


@pytest.fixture(autouse=True)
async def _ensure_checkpoint_tables() -> None:
    await setup_checkpointer_tables()


async def test_worker_restart_resumes_without_rerunning_completed_node() -> None:
    _TrackingAdapter.calls = []
    llm_client = LLMClient(adapter_factory=_TrackingAdapter)
    thread_id = str(uuid.uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    initial_state: CaseState = {"document_text": "some claim text"}

    # Simulate a worker that completes "intake" then dies before "validate" runs.
    async with get_checkpointer() as checkpointer:
        graph = compile_graph(
            llm_client, _FakeRetriever(), checkpointer, interrupt_after=["intake"]
        )
        state_after_crash = await graph.ainvoke(initial_state, config=config)

    assert state_after_crash["status"] == "validating"
    assert _TrackingAdapter.calls == ["ClaimFields"]

    # Simulate a fresh worker process picking the same case back up from its
    # checkpoint — passing None as input resumes rather than restarting.
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy_number": "POL-AUTO-001",
                    "customer_id": "cust-1001",
                    "status": "active",
                    "category": "auto",
                    "coverage_limit": 25000.0,
                    "effective_date": "2025-01-01",
                    "expiry_date": "2026-12-31",
                },
            )
        )
        async with get_checkpointer() as checkpointer:
            graph = compile_graph(llm_client, _FakeRetriever(), checkpointer)
            final_state = await graph.ainvoke(None, config=config)

    assert final_state["status"] == "drafted"
    assert final_state["draft"]["decision"] == "approve"
    # intake must not have re-run on resume; only validate -> draft should have executed
    assert _TrackingAdapter.calls == ["ClaimFields", "DecisionDraft"]
