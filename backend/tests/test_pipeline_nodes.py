import httpx
import respx
from pydantic import BaseModel

from app.llm.adapters import TokenUsage
from app.llm.client import LLMClient
from app.pipeline.nodes.draft import run_draft
from app.pipeline.nodes.intake import run_intake
from app.pipeline.nodes.validate import run_validate
from app.pipeline.state import CaseState

CRM_BASE = "http://localhost:8001"


class _FakeIntakeAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        data = schema(
            claimant_name="Jane Doe",
            policy_number="POL-AUTO-001",
            incident_date="2026-01-05",
            claimed_amount="1200.00",
            category="auto",
            description="Rear-end collision",
        )
        return data, TokenUsage(input_tokens=200, output_tokens=80)


class _FakeDraftAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        data = schema(
            decision="approve",
            payout_amount="1200.00",
            reasoning="Validation passed and evidence supports coverage.",
            citations=["clause-1"],
            confidence=0.9,
        )
        return data, TokenUsage(input_tokens=300, output_tokens=120)


async def test_run_intake_extracts_fields() -> None:
    llm_client = LLMClient(adapter_factory=_FakeIntakeAdapter)
    state: CaseState = {"document_text": "some claim text"}
    update = await run_intake(state, llm_client=llm_client)

    assert update["extracted_fields"]["claimant_name"] == "Jane Doe"
    assert update["extracted_fields"]["policy_number"] == "POL-AUTO-001"
    assert update["status"] == "validating"
    assert update["model_versions"]["intake"]
    assert update["prompt_versions"]["intake"] == "v1"
    assert update["token_cost_usd"] >= 0


async def test_run_validate_active_policy_is_valid() -> None:
    fields = {
        "claimant_name": "Jane Doe",
        "policy_number": "POL-AUTO-001",
        "incident_date": "2026-01-05",
        "claimed_amount": "1200.00",
        "category": "auto",
        "description": "Rear-end collision",
    }
    state: CaseState = {"extracted_fields": fields}

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
        update = await run_validate(state)

    assert update["validation_result"]["valid"] is True
    assert update["status"] == "validated"


async def test_run_validate_missing_fields_needs_info() -> None:
    state: CaseState = {"extracted_fields": {}}
    update = await run_validate(state)

    assert update["validation_result"]["valid"] is False
    assert update["status"] == "needs_info"
    assert any(
        "missing required field" in reason for reason in update["validation_result"]["reasons"]
    )


async def test_run_validate_lapsed_policy_is_invalid() -> None:
    fields = {
        "claimant_name": "Priya Nair",
        "policy_number": "POL-HEALTH-003",
        "incident_date": "2026-01-05",
        "claimed_amount": "500.00",
        "category": "health",
        "description": "checkup",
    }
    state: CaseState = {"extracted_fields": fields}

    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-HEALTH-003").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy_number": "POL-HEALTH-003",
                    "customer_id": "cust-1003",
                    "status": "lapsed",
                    "category": "health",
                    "coverage_limit": 50000.0,
                    "effective_date": "2023-01-01",
                    "expiry_date": "2024-01-01",
                },
            )
        )
        update = await run_validate(state)

    assert update["validation_result"]["valid"] is False
    assert any("lapsed" in reason for reason in update["validation_result"]["reasons"])


async def test_run_validate_unknown_policy_is_invalid() -> None:
    fields = {
        "claimant_name": "Jane Doe",
        "policy_number": "POL-DOES-NOT-EXIST",
        "incident_date": "2026-01-05",
        "claimed_amount": "1200.00",
        "category": "auto",
        "description": "Rear-end collision",
    }
    state: CaseState = {"extracted_fields": fields}

    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/POL-DOES-NOT-EXIST").mock(return_value=httpx.Response(404))
        update = await run_validate(state)

    assert update["validation_result"]["valid"] is False
    assert any("not found" in reason for reason in update["validation_result"]["reasons"])


async def test_run_draft_produces_decision() -> None:
    llm_client = LLMClient(adapter_factory=_FakeDraftAdapter)
    state: CaseState = {
        "extracted_fields": {"category": "auto", "claimed_amount": "1200.00"},
        "validation_result": {"valid": True, "reasons": [], "policy_status": "active"},
        "evidence": [
            {
                "clause_id": "clause-1",
                "text": "Auto claims covered up to $25,000",
                "similarity": 0.9,
            }
        ],
    }
    update = await run_draft(state, llm_client=llm_client)

    assert update["draft"]["decision"] == "approve"
    assert update["status"] == "drafted"
    assert update["model_versions"]["draft"]
