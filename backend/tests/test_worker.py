import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.db.session import session_factory
from app.llm.adapters import StructuredOutputError, TokenUsage
from app.llm.client import LLMClient
from app.models.case import Case
from app.pipeline.checkpointer import setup_checkpointer_tables
from app.pipeline.schemas import Evidence
from app.worker import run_case_pipeline

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


class _HappyPathAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
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


class _AlwaysFailsAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        raise StructuredOutputError("boom")


async def _create_case(document_text: str) -> uuid.UUID:
    async with session_factory() as session:
        case = Case(
            document_hash=str(uuid.uuid4()), document_text=document_text, status="queued"
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)
        return case.id


async def test_run_case_pipeline_happy_path_updates_case() -> None:
    await setup_checkpointer_tables()
    case_id = await _create_case("some claim text")
    llm_client = LLMClient(adapter_factory=_HappyPathAdapter)

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
        await run_case_pipeline({}, str(case_id), llm_client=llm_client, retriever=_FakeRetriever())

    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.status == "drafted"
        assert case.draft is not None
        assert case.draft["decision"] == "approve"
        assert case.evidence is not None
        assert case.evidence[0]["clause_id"] == "AUTO-001"
        assert case.token_cost_usd >= Decimal("0")


async def test_run_case_pipeline_records_error_on_failure() -> None:
    await setup_checkpointer_tables()
    case_id = await _create_case("some claim text")
    llm_client = LLMClient(adapter_factory=_AlwaysFailsAdapter)

    with pytest.raises(Exception, match="exhausted"):
        await run_case_pipeline({}, str(case_id), llm_client=llm_client, retriever=_FakeRetriever())

    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.status == "error"
        assert case.errors
