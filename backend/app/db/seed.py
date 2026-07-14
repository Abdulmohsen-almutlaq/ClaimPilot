import asyncio

from sqlalchemy.dialects.postgresql import insert

from app.auth.security import hash_password
from app.db.session import session_factory
from app.models.user import User

_DEMO_USERS = [
    ("submitter@demo.io", "demo", "submitter"),
    ("approver@demo.io", "demo", "approver"),
    ("admin@demo.io", "demo", "admin"),
]


async def seed_users() -> None:
    async with session_factory() as session:
        for email, password, role in _DEMO_USERS:
            stmt = (
                insert(User)
                .values(email=email, password_hash=hash_password(password), role=role)
                .on_conflict_do_nothing(index_elements=["email"])
            )
            await session.execute(stmt)
        await session.commit()


def main() -> None:
    asyncio.run(seed_users())


if __name__ == "__main__":
    main()
