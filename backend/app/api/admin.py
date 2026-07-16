import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.security import hash_password
from app.auth.users import Role
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


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=4, max_length=128)
    role: Role

    @field_validator("email")
    @classmethod
    def _basic_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("not an email address")
        return value


class UserRoleRequest(BaseModel):
    role: Role


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id), email=user.email, role=user.role, created_at=user.created_at
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> list[UserResponse]:
    users = (await session.execute(select(User).order_by(User.created_at))).scalars().all()
    return [_user_response(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    existing = await session.scalar(select(User).where(User.email == request.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already exists")
    created = User(
        email=request.email, password_hash=hash_password(request.password), role=request.role
    )
    session.add(created)
    await session.commit()
    await session.refresh(created)
    return _user_response(created)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    request: UserRoleRequest,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    # An admin locking themselves out mid-session is unrecoverable from the UI.
    if target.email == user.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="cannot change your own role"
        )
    target.role = request.role
    await session.commit()
    return _user_response(target)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> None:
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if target.email == user.email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot delete yourself")
    await session.delete(target)
    await session.commit()
