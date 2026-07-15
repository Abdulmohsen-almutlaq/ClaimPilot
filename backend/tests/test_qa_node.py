from fakes import QA_ALL_PASS, SchemaAwareAdapter, qa_fail

from app.llm.client import LLMClient
from app.pipeline.nodes.qa import run_qa
from app.pipeline.state import CaseState

_STATE: CaseState = {
    "extracted_fields": {"category": "auto", "claimed_amount": "1200.00"},
    "validation_result": {"valid": True, "reasons": [], "policy_status": "active"},
    "evidence": [{"clause_id": "AUTO-001", "text": "Collision coverage.", "similarity": 0.9}],
    "draft": {
        "decision": "approve",
        "payout_amount": "700.00",
        "reasoning": "Covered per AUTO-001.",
        "citations": ["AUTO-001"],
        "confidence": 0.9,
    },
}


async def test_model_passed_aggregate_is_never_trusted() -> None:
    # The model claims passed=True while reporting a failed sub-check; the node
    # must recompute the aggregate from the sub-checks (principle 1).
    lying_qa = {**QA_ALL_PASS, "passed": True, "decision_consistent": False}
    SchemaAwareAdapter.reset(qa_results=[lying_qa])
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)

    update = await run_qa(_STATE, llm_client=llm_client)

    assert update["qa_result"]["passed"] is False
    assert update["status"] == "qa_failed"


async def test_failed_qa_increments_attempts() -> None:
    SchemaAwareAdapter.reset(qa_results=[qa_fail("cite the deductible clause")])
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)

    update = await run_qa({**_STATE, "qa_attempts": 1}, llm_client=llm_client)

    assert update["qa_attempts"] == 2
    assert update["qa_result"]["reasons"] == ["cite the deductible clause"]


async def test_passed_qa_sets_status_and_bookkeeping() -> None:
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)

    update = await run_qa(_STATE, llm_client=llm_client)

    assert update["status"] == "qa_passed"
    assert update["qa_attempts"] == 1
    assert update["model_versions"]["qa"]
    # tracks the active version in models.yaml; the point is that it's recorded
    assert update["prompt_versions"]["qa"]
    assert update["tokens_used"] == 15
