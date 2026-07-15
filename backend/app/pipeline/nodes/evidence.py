from typing import Any

from app.pipeline.schemas import ClaimFields
from app.pipeline.state import CaseState
from app.rag.retrieve import Retriever


def _build_query(fields: ClaimFields) -> str:
    parts = [
        f"{fields.category} insurance claim" if fields.category else "insurance claim",
        fields.description or "",
        f"claimed amount {fields.claimed_amount}" if fields.claimed_amount is not None else "",
    ]
    return " ".join(part for part in parts if part).strip()


async def run_evidence(state: CaseState, *, retriever: Retriever) -> dict[str, Any]:
    fields = ClaimFields.model_validate(state.get("extracted_fields") or {})
    evidence = await retriever.retrieve(_build_query(fields), category=fields.category)

    if not evidence:
        # Spec 5.1: no relevant evidence is never auto-decided — flag for a human.
        return {"evidence": [], "status": "human_queue", "route": "human_queue"}

    return {
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "status": "evidence_retrieved",
    }
