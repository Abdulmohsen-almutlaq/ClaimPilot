import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.audit.writer import get_audit_trail, write_audit_event
from app.db.session import session_factory
from app.models.case import Case


@pytest.fixture
async def case_id() -> AsyncGenerator[uuid.UUID]:
    async with session_factory() as session:
        case = Case(document_hash=str(uuid.uuid4()))
        session.add(case)
        await session.commit()
        await session.refresh(case)
        yield case.id


async def test_write_and_read_audit_trail(case_id: uuid.UUID) -> None:
    async with session_factory() as session:
        await write_audit_event(
            session, case_id=case_id, actor="system", event_type="node_start", node="intake"
        )

    async with session_factory() as session:
        trail = await get_audit_trail(session, case_id)
    assert len(trail) == 1
    assert trail[0].event_type == "node_start"
    assert trail[0].node == "intake"


async def test_audit_log_update_is_rejected(case_id: uuid.UUID) -> None:
    async with session_factory() as session:
        entry = await write_audit_event(
            session, case_id=case_id, actor="system", event_type="node_start"
        )

    async with session_factory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(
                text("UPDATE audit_log SET actor = 'tampered' WHERE id = :id"), {"id": entry.id}
            )
            await session.commit()


async def test_audit_log_delete_is_rejected(case_id: uuid.UUID) -> None:
    async with session_factory() as session:
        entry = await write_audit_event(
            session, case_id=case_id, actor="system", event_type="node_start"
        )

    async with session_factory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": entry.id})
            await session.commit()
