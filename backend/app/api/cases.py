import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.users import User
from app.db.session import get_session
from app.models.case import Case
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
    route: str | None


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
        route=case.route,
    )
