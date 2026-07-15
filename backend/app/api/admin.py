import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.core.dlq import list_dlq, pop_dlq_entry
from app.db.session import get_session
from app.models.case import Case
from app.models.user import User
from app.worker import enqueue_case_pipeline

router = APIRouter(prefix="/admin", tags=["admin"])


class DLQEntryResponse(BaseModel):
    case_id: str
    error: str
    traceback: str
    failed_at: str


class RequeueResponse(BaseModel):
    case_id: str
    status: str


@router.get("/dlq", response_model=list[DLQEntryResponse])
async def get_dlq(user: User = Depends(require_role("admin"))) -> list[dict[str, Any]]:
    return await list_dlq()


@router.post("/dlq/{case_id}/requeue", response_model=RequeueResponse)
async def requeue_dlq_case(
    case_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> RequeueResponse:
    entry = await pop_dlq_entry(str(case_id))
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="case not in dead-letter queue"
        )

    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    case.status = "queued"
    await session.commit()

    await enqueue_case_pipeline(str(case_id))
    return RequeueResponse(case_id=str(case_id), status="queued")
