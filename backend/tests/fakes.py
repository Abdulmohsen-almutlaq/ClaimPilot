"""Shared test fakes. They substitute at the same seams production code uses
(adapter_factory / retriever params) — no monkeypatching (principle 2)."""

from typing import Any

from pydantic import BaseModel

from app.llm.adapters import TokenUsage
from app.pipeline.schemas import Evidence

QA_ALL_PASS: dict[str, Any] = {
    "passed": True,
    "claims_supported": True,
    "citations_relevant": True,
    "decision_consistent": True,
    "professional_tone": True,
    "reasons": [],
}


def qa_fail(*reasons: str) -> dict[str, Any]:
    return {
        "passed": False,
        "claims_supported": False,
        "citations_relevant": True,
        "decision_consistent": True,
        "professional_tone": True,
        "reasons": list(reasons),
    }


class SchemaAwareAdapter:
    """Fake LLM adapter that shapes valid output per requested schema and records
    every call. QA outcomes are scriptable via `qa_results` (a queue of QAResult
    kwargs); defaults to all-pass. Call reset() at the start of each test."""

    calls: list[str] = []
    draft_prompts: list[str] = []
    qa_results: list[dict[str, Any]] = []

    def __init__(self, **kwargs: object) -> None:
        pass

    @classmethod
    def reset(cls, qa_results: list[dict[str, Any]] | None = None) -> None:
        cls.calls = []
        cls.draft_prompts = []
        cls.qa_results = list(qa_results or [])

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        name = schema.__name__
        SchemaAwareAdapter.calls.append(name)
        data: BaseModel
        if name == "ClaimFields":
            data = schema(
                claimant_name="Jane Doe",
                policy_number="POL-AUTO-001",
                incident_date="2026-01-05",
                claimed_amount="1200.00",
                category="auto",
                description="Rear-end collision",
            )
        elif name == "DecisionDraft":
            SchemaAwareAdapter.draft_prompts.append(user_prompt)
            data = schema(
                decision="approve",
                payout_amount="1200.00",
                reasoning="Validation passed and evidence supports coverage.",
                citations=["AUTO-001"],
                confidence=0.9,
            )
        elif name == "QAResult":
            kwargs = (
                SchemaAwareAdapter.qa_results.pop(0)
                if SchemaAwareAdapter.qa_results
                else QA_ALL_PASS
            )
            data = schema(**kwargs)
        else:
            raise AssertionError(f"unexpected schema requested: {name}")
        return data, TokenUsage(input_tokens=10, output_tokens=5)


class FakeRetriever:
    async def retrieve(self, query: str, *, category: str | None = None) -> list[Evidence]:
        return [
            Evidence(
                clause_id="AUTO-001",
                text="Collision coverage up to $25,000.",
                similarity=0.9,
            )
        ]


ACTIVE_AUTO_POLICY: dict[str, Any] = {
    "policy_number": "POL-AUTO-001",
    "customer_id": "cust-1001",
    "status": "active",
    "category": "auto",
    "coverage_limit": 25000.0,
    "effective_date": "2025-01-01",
    "expiry_date": "2026-12-31",
}
