from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, verify_password
from app.auth.users import get_user_by_email
from app.config import Settings, get_settings
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    email: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    user = await get_user_by_email(session, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.email, user.role, settings)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(email=user.email, role=user.role)
