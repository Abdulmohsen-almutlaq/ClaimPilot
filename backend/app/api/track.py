import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.case import Case

router = APIRouter(prefix="/track", tags=["track"])

# Coarse claimant-facing phases: never expose internal states (error, drafted,
# DLQ) to an unauthenticated caller.
_PHASES = {
    "human_queue": "in_review",
    "auto_approved": "approved",
    "approved": "approved",
    "rejected": "rejected",
    "needs_info": "needs_info",
}


class TrackResponse(BaseModel):
    case_id: str
    phase: str
    submitted_at: datetime
    decided_at: datetime | None


@router.get("/{case_id}", response_model=TrackResponse)
async def track_case(
    case_id: uuid.UUID,
    policy_number: str = Query(min_length=1, max_length=64),
    session: AsyncSession = Depends(get_session),
) -> TrackResponse:
    """Public claim tracking: requires both the case id and the policy number
    on the claim, and answers 404 identically for wrong-id and wrong-policy so
    case existence is never revealed."""
    case = await session.get(Case, case_id)
    stored = str((case.extracted_fields or {}).get("policy_number") or "") if case else ""
    if not stored or stored.strip().lower() != policy_number.strip().lower():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no matching claim")
    assert case is not None
    phase = _PHASES.get(case.status, "processing")
    return TrackResponse(
        case_id=str(case.id),
        phase=phase,
        submitted_at=case.created_at,
        decided_at=case.decided_at if phase in ("approved", "rejected") else None,
    )
