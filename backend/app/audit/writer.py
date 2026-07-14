import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_audit_event(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    actor: str,
    event_type: str,
    node: str | None = None,
    model: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
    input_hash: str | None = None,
    output_hash: str | None = None,
    payload: dict[str, Any] | None = None,
    cost_usd: Decimal | None = None,
    latency_ms: int | None = None,
) -> AuditLog:
    entry = AuditLog(
        case_id=case_id,
        actor=actor,
        event_type=event_type,
        node=node,
        model=model,
        model_version=model_version,
        prompt_version=prompt_version,
        input_hash=input_hash,
        output_hash=output_hash,
        payload_json=payload,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_audit_trail(session: AsyncSession, case_id: uuid.UUID) -> list[AuditLog]:
    result = await session.execute(
        select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.timestamp)
    )
    return list(result.scalars().all())
