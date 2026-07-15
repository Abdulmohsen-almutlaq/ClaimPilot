import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from fakes import ACTIVE_AUTO_POLICY, FakeRetriever, SchemaAwareAdapter
from pydantic import BaseModel

from app.audit.writer import get_audit_trail
from app.db.session import session_factory
from app.llm.adapters import StructuredOutputError, TokenUsage
from app.llm.client import LLMClient
from app.models.case import Case
from app.pipeline.checkpointer import setup_checkpointer_tables
from app.worker import run_case_pipeline

CRM_BASE = "http://localhost:8001"


class _AlwaysFailsAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        raise StructuredOutputError("boom")


async def _create_case(document_text: str, *, tokens_used: int = 0) -> uuid.UUID:
    async with session_factory() as session:
        case = Case(
            document_hash=str(uuid.uuid4()),
            document_text=document_text,
            status="queued",
            tokens_used=tokens_used,
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)
        return case.id


async def test_run_case_pipeline_happy_path_updates_case() -> None:
    await setup_checkpointer_tables()
    case_id = await _create_case("some claim text")
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)

    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-AUTO-001").mock(
            return_value=httpx.Response(200, json=ACTIVE_AUTO_POLICY)
        )
        await run_case_pipeline({}, str(case_id), llm_client=llm_client, retriever=FakeRetriever())

    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.status == "auto_approved"
        assert case.route == "auto_approve"
        assert case.route_reason is None
        assert case.draft is not None
        assert case.draft["decision"] == "approve"
        assert case.qa_result is not None
        assert case.qa_result["passed"] is True
        assert case.evidence is not None
        assert case.evidence[0]["clause_id"] == "AUTO-001"
        assert case.token_cost_usd >= Decimal("0")
        assert case.tokens_used == 45  # intake + draft + qa

    # Every state transition must land in the append-only audit trail.
    async with session_factory() as session:
        events = [(e.event_type, e.node) for e in await get_audit_trail(session, case_id)]
    assert events[0] == ("pipeline_started", None)
    for node in ("intake", "validate", "evidence", "draft", "qa", "route"):
        assert ("node_completed", node) in events
    assert events[-1] == ("pipeline_completed", None)


async def test_run_case_pipeline_records_error_on_failure() -> None:
    await setup_checkpointer_tables()
    case_id = await _create_case("some claim text")
    llm_client = LLMClient(adapter_factory=_AlwaysFailsAdapter)

    with pytest.raises(Exception, match="exhausted"):
        await run_case_pipeline({}, str(case_id), llm_client=llm_client, retriever=FakeRetriever())

    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.status == "error"
        assert case.errors

    async with session_factory() as session:
        events = [e.event_type for e in await get_audit_trail(session, case_id)]
    assert events[0] == "pipeline_started"
    assert events[-1] == "pipeline_failed"


async def test_budget_exhausted_routes_to_human_without_crashing() -> None:
    await setup_checkpointer_tables()
    # A case that already burned far past the hard token limit: the very first
    # LLM call must be refused and the case handed to a human — no exception,
    # no stuck "queued" status, no wasted spend.
    case_id = await _create_case("some claim text", tokens_used=10_000_000)
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)

    await run_case_pipeline({}, str(case_id), llm_client=llm_client, retriever=FakeRetriever())

    assert SchemaAwareAdapter.calls == []  # refused before any model was invoked
    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.status == "human_queue"
        assert case.route == "human_queue"
        assert case.route_reason == "budget_exhausted"

    async with session_factory() as session:
        events = [e.event_type for e in await get_audit_trail(session, case_id)]
    assert events[-1] == "budget_exhausted"
