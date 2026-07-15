"""Route-node tests — failure paths first, per the spec's own M5 instruction.
Pure Python, no LLM, no DB: the final gate before money moves must be
deterministic and exhaustively unit-testable."""

from typing import Any

from app.pipeline.nodes.route import run_route
from app.pipeline.state import CaseState

_QA_PASS: dict[str, Any] = {
    "passed": True,
    "claims_supported": True,
    "citations_relevant": True,
    "decision_consistent": True,
    "professional_tone": True,
    "reasons": [],
}
_QA_FAIL = {**_QA_PASS, "passed": False, "claims_supported": False}


def _state(
    *,
    decision: str = "approve",
    payout: str | None = "2950.00",
    claimed: str | None = "3450.00",
    confidence: float = 0.9,
    qa: dict[str, Any] | None = None,
) -> CaseState:
    return {
        "draft": {
            "decision": decision,
            "payout_amount": payout,
            "reasoning": "r",
            "citations": ["AUTO-001"],
            "confidence": confidence,
        },
        "extracted_fields": {"claimed_amount": claimed, "category": "auto"},
        "qa_result": qa if qa is not None else _QA_PASS,
    }


async def test_reject_decision_routes_to_human() -> None:
    update = await run_route(_state(decision="reject"))
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "decision_reject"


async def test_needs_info_decision_routes_to_human() -> None:
    update = await run_route(_state(decision="needs_info", payout=None))
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "decision_needs_info"


async def test_failed_qa_routes_to_human_even_when_amount_and_confidence_pass() -> None:
    update = await run_route(_state(qa=_QA_FAIL))
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "qa_failed"


async def test_missing_qa_result_never_auto_approves() -> None:
    state = _state()
    state["qa_result"] = None
    update = await run_route(state)
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "qa_failed"


async def test_amount_above_threshold_routes_to_human() -> None:
    update = await run_route(_state(payout="6000.00"))
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "amount_above_threshold"


async def test_unknown_amount_routes_to_human() -> None:
    update = await run_route(_state(payout=None, claimed=None))
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "amount_unknown"


async def test_low_confidence_routes_to_human() -> None:
    update = await run_route(_state(confidence=0.7))
    assert update["route"] == "human_queue"
    assert update["route_reason"] == "low_confidence"


async def test_all_conditions_met_auto_approves() -> None:
    update = await run_route(_state())
    assert update["route"] == "auto_approve"
    assert update["route_reason"] is None
    assert update["status"] == "auto_approved"


async def test_payout_amount_preferred_over_claimed_amount() -> None:
    # claimed $8,000 exceeds the $5,000 threshold, but the drafted payout
    # ($2,950 after deductible) is what would actually move — that's the risk.
    update = await run_route(_state(payout="2950.00", claimed="8000.00"))
    assert update["route"] == "auto_approve"
