import uuid

import httpx
import pytest
import respx
from fakes import ACTIVE_AUTO_POLICY, FakeRetriever, SchemaAwareAdapter
from langchain_core.runnables import RunnableConfig

from app.llm.client import LLMClient
from app.pipeline.checkpointer import get_checkpointer, setup_checkpointer_tables
from app.pipeline.graph import compile_graph
from app.pipeline.state import CaseState

CRM_BASE = "http://localhost:8001"


@pytest.fixture(autouse=True)
async def _ensure_checkpoint_tables() -> None:
    await setup_checkpointer_tables()


async def test_worker_restart_resumes_without_rerunning_completed_node() -> None:
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)
    thread_id = str(uuid.uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    initial_state: CaseState = {"document_text": "some claim text"}

    # Simulate a worker that completes "intake" then dies before "validate" runs.
    async with get_checkpointer() as checkpointer:
        graph = compile_graph(
            llm_client, FakeRetriever(), checkpointer, interrupt_after=["intake"]
        )
        state_after_crash = await graph.ainvoke(initial_state, config=config)

    assert state_after_crash["status"] == "validating"
    assert SchemaAwareAdapter.calls == ["ClaimFields"]

    # Simulate a fresh worker process picking the same case back up from its
    # checkpoint — passing None as input resumes rather than restarting.
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(
            return_value=httpx.Response(200, json=ACTIVE_AUTO_POLICY)
        )
        async with get_checkpointer() as checkpointer:
            graph = compile_graph(llm_client, FakeRetriever(), checkpointer)
            final_state = await graph.ainvoke(None, config=config)

    # intake must not have re-run on resume; only the downstream LLM nodes did
    assert SchemaAwareAdapter.calls == ["ClaimFields", "DecisionDraft", "QAResult"]
    assert final_state["status"] == "auto_approved"
    assert final_state["route"] == "auto_approve"
    assert final_state["draft"]["decision"] == "approve"
