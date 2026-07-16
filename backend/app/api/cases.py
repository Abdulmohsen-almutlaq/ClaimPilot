import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.writer import get_audit_trail, write_audit_event
from app.auth.dependencies import require_role
from app.db.session import get_session
from app.models.case import Case
from app.models.user import User
from app.tools.parser import extract_text_from_pdf
from app.worker import enqueue_case_pipeline

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreatedResponse(BaseModel):
    case_id: str
    status: str


class CaseDetailResponse(BaseModel):
    case_id: str
    status: str
    extracted_fields: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    draft: dict[str, Any] | None
    qa_result: dict[str, Any] | None
    route: str | None
    route_reason: str | None
    human_decision: str | None
    overridden: bool | None
    decided_by: str | None
    decided_at: datetime | None


class CaseSummaryResponse(BaseModel):
    """One approval-queue row: enough for a reviewer to pick a case, no more."""

    case_id: str
    status: str
    route_reason: str | None
    claimant_name: str | None
    claimed_amount: str | None
    category: str | None
    created_at: datetime


@router.post("", response_model=CaseCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    file: UploadFile,
    user: User = Depends(require_role("submitter", "admin")),
    session: AsyncSession = Depends(get_session),
) -> CaseCreatedResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")

    document_hash = hashlib.sha256(data).hexdigest()

    existing = await session.scalar(select(Case).where(Case.document_hash == document_hash))
    if existing is not None:
        return CaseCreatedResponse(case_id=str(existing.id), status=existing.status)

    document_text = extract_text_from_pdf(data)
    case = Case(document_hash=document_hash, document_text=document_text, status="queued")
    session.add(case)
    await session.commit()
    await session.refresh(case)

    await enqueue_case_pipeline(str(case.id))

    return CaseCreatedResponse(case_id=str(case.id), status=case.status)


@router.get("", response_model=list[CaseSummaryResponse])
async def list_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(require_role("approver", "admin")),
    session: AsyncSession = Depends(get_session),
) -> list[CaseSummaryResponse]:
    """Approval-queue feed: `GET /cases?status=human_queue`, oldest first."""
    query = select(Case).order_by(Case.created_at).limit(limit)
    if status_filter is not None:
        query = query.where(Case.status == status_filter)
    cases = (await session.execute(query)).scalars().all()

    summaries: list[CaseSummaryResponse] = []
    for case in cases:
        fields = case.extracted_fields or {}
        amount = fields.get("claimed_amount")
        summaries.append(
            CaseSummaryResponse(
                case_id=str(case.id),
                status=case.status,
                route_reason=case.route_reason,
                claimant_name=fields.get("claimant_name"),
                claimed_amount=str(amount) if amount is not None else None,
                category=fields.get("category"),
                created_at=case.created_at,
            )
        )
    return summaries


@router.get("/{case_id}", response_model=CaseDetailResponse)
async def get_case(
    case_id: uuid.UUID,
    user: User = Depends(require_role("submitter", "approver", "admin")),
    session: AsyncSession = Depends(get_session),
) -> CaseDetailResponse:
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    return CaseDetailResponse(
        case_id=str(case.id),
        status=case.status,
        extracted_fields=case.extracted_fields,
        validation_result=case.validation_result,
        draft=case.draft,
        qa_result=case.qa_result,
        route=case.route,
        route_reason=case.route_reason,
        human_decision=case.human_decision,
        overridden=case.overridden,
        decided_by=case.decided_by,
        decided_at=case.decided_at,
    )


class DecisionRequest(BaseModel):
    # Same vocabulary as DecisionDraft.decision, so the override comparison
    # (human vs AI) is an exact string match — "deny" vs "reject" would count
    # agreement as an override.
    decision: Literal["approve", "reject"]
    notes: str | None = None


class DecisionResponse(BaseModel):
    case_id: str
    status: str
    human_decision: str
    ai_decision: str | None
    overridden: bool


@router.post("/{case_id}/decision", response_model=DecisionResponse)
async def decide_case(
    case_id: uuid.UUID,
    request: DecisionRequest,
    user: User = Depends(require_role("approver", "admin")),
    session: AsyncSession = Depends(get_session),
) -> DecisionResponse:
    """Human decision on a queued case. An override (human disagreeing with the
    AI draft) is computed server-side and recorded immutably in the audit log —
    it is the M7 KPI that tells us whether the model can be trusted."""
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    if case.status != "human_queue":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"case is not awaiting a decision (status: {case.status})",
        )

    ai_decision: str | None = (case.draft or {}).get("decision")
    overridden = ai_decision is not None and request.decision != ai_decision

    case.human_decision = request.decision
    case.decision_notes = request.notes
    case.decided_by = user.email
    case.decided_at = datetime.now(UTC)
    case.overridden = overridden
    case.status = "approved" if request.decision == "approve" else "rejected"

    # write_audit_event commits, so the case update and its audit entry land
    # in one transaction — a decision without a trail must be impossible.
    await write_audit_event(
        session,
        case_id=case.id,
        actor=user.email,
        event_type="human_decision",
        node="decision",
        payload={
            "decision": request.decision,
            "ai_decision": ai_decision,
            "overridden": overridden,
            "notes": request.notes,
            "route_reason": case.route_reason,
        },
    )

    return DecisionResponse(
        case_id=str(case.id),
        status=case.status,
        human_decision=request.decision,
        ai_decision=ai_decision,
        overridden=overridden,
    )


class AuditEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    actor: str
    event_type: str
    node: str | None
    model: str | None
    model_version: str | None
    prompt_version: str | None
    input_hash: str | None
    output_hash: str | None
    payload: dict[str, Any] | None
    cost_usd: Decimal | None
    latency_ms: int | None


@router.get("/{case_id}/audit", response_model=list[AuditEntryResponse])
async def get_case_audit(
    case_id: uuid.UUID,
    user: User = Depends(require_role("approver", "admin")),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEntryResponse]:
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    entries = await get_audit_trail(session, case_id)
    return [
        AuditEntryResponse(
            id=str(entry.id),
            timestamp=entry.timestamp,
            actor=entry.actor,
            event_type=entry.event_type,
            node=entry.node,
            model=entry.model,
            model_version=entry.model_version,
            prompt_version=entry.prompt_version,
            input_hash=entry.input_hash,
            output_hash=entry.output_hash,
            payload=entry.payload_json,
            cost_usd=entry.cost_usd,
            latency_ms=entry.latency_ms,
        )
        for entry in entries
    ]
