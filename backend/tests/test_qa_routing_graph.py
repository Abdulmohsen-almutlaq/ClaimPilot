"""End-to-end graph tests for the QA regenerate loop and routing (compiled
without a checkpointer; validate reads the conftest-seeded POL-AUTO-001 row)."""

from fakes import FakeRetriever, SchemaAwareAdapter, qa_fail

from app.llm.client import LLMClient
from app.pipeline.graph import compile_graph
from app.pipeline.state import CaseState

_INITIAL: CaseState = {"document_text": "some claim text"}


async def test_qa_failing_twice_routes_to_human_after_one_regen() -> None:
    SchemaAwareAdapter.reset(
        qa_results=[qa_fail("payout must subtract the deductible"), qa_fail("still wrong")]
    )
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)
    graph = compile_graph(llm_client, FakeRetriever(), None)

    final = await graph.ainvoke(_INITIAL)

    # exactly one regenerate: draft, qa, draft again, qa again — then stop
    assert SchemaAwareAdapter.calls == [
        "ClaimFields",
        "DecisionDraft",
        "QAResult",
        "DecisionDraft",
        "QAResult",
    ]
    assert final["route"] == "human_queue"
    assert final["route_reason"] == "qa_failed"
    assert final["status"] == "human_queue"


async def test_regenerated_draft_receives_qa_feedback_verbatim() -> None:
    SchemaAwareAdapter.reset(qa_results=[qa_fail("payout must subtract the deductible")])
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)
    graph = compile_graph(llm_client, FakeRetriever(), None)

    final = await graph.ainvoke(_INITIAL)

    assert len(SchemaAwareAdapter.draft_prompts) == 2
    first, second = SchemaAwareAdapter.draft_prompts
    assert "qa_feedback" not in first
    assert "qa_feedback" in second
    assert "payout must subtract the deductible" in second
    # second QA attempt passed (default all-pass), so the case auto-approves
    assert final["route"] == "auto_approve"
    assert final["status"] == "auto_approved"


async def test_qa_passing_first_time_auto_approves_without_regen() -> None:
    SchemaAwareAdapter.reset()
    llm_client = LLMClient(adapter_factory=SchemaAwareAdapter)
    graph = compile_graph(llm_client, FakeRetriever(), None)

    final = await graph.ainvoke(_INITIAL)

    assert SchemaAwareAdapter.calls == ["ClaimFields", "DecisionDraft", "QAResult"]
    assert final["route"] == "auto_approve"
    assert final["qa_result"]["passed"] is True
    assert final["tokens_used"] == 45  # 3 LLM calls x 15 tokens each
