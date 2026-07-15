from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

Role = Literal["submitter", "approver", "admin"]


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    user: User | None = await session.scalar(select(User).where(User.email == email))
    return user
