from decimal import Decimal
from typing import Any

from app.pipeline.domain_config import load_domain_config
from app.pipeline.schemas import ClaimFields, DecisionDraft, QAResult
from app.pipeline.state import CaseState


def _amount_at_stake(draft: DecisionDraft, fields: ClaimFields) -> Decimal | None:
    if draft.payout_amount is not None:
        return draft.payout_amount
    return fields.claimed_amount


async def run_route(state: CaseState) -> dict[str, Any]:
    """Pure Python routing — deliberately no LLM (spec 5.1): the final gate before
    money moves must be deterministic, auditable, and unit-testable. Returns the
    FIRST failing condition as route_reason so the approval queue shows a human
    exactly why the case landed there."""
    thresholds = load_domain_config()["risk_thresholds"]
    max_amount = Decimal(str(thresholds["auto_approve_max_amount"]))
    min_confidence = float(thresholds["auto_approve_min_confidence"])

    draft = DecisionDraft.model_validate(state.get("draft") or {})
    fields = ClaimFields.model_validate(state.get("extracted_fields") or {})
    qa = QAResult.model_validate(
        state.get("qa_result")
        or {
            "passed": False,
            "claims_supported": False,
            "citations_relevant": False,
            "decision_consistent": False,
            "professional_tone": False,
        }
    )
    amount = _amount_at_stake(draft, fields)

    reason: str | None = None
    if draft.decision != "approve":
        reason = f"decision_{draft.decision}"
    elif not qa.passed:
        reason = "qa_failed"
    elif amount is None:
        reason = "amount_unknown"
    elif amount > max_amount:
        reason = "amount_above_threshold"
    elif draft.confidence < min_confidence:
        reason = "low_confidence"

    if reason is not None:
        return {"route": "human_queue", "route_reason": reason, "status": "human_queue"}
    return {"route": "auto_approve", "route_reason": None, "status": "auto_approved"}
