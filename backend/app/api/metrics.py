from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.session import get_session
from app.models.case import Case
from app.models.user import User

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Statuses where processing has finished and an outcome exists. automation_rate
# is measured against these only — in-flight cases would dilute the KPI.
_TERMINAL_STATUSES = ("auto_approved", "approved", "rejected")


class MetricsResponse(BaseModel):
    total_cases: int
    cases_by_status: dict[str, int]
    human_queue_depth: int
    automation_rate: float | None
    override_rate: float | None
    human_decided_cases: int
    overridden_cases: int
    total_tokens: int
    total_token_cost_usd: float
    avg_tokens_per_case: float | None
    avg_cost_per_case_usd: float | None


@router.get("", response_model=MetricsResponse)
async def get_metrics(
    user: User = Depends(require_role("approver", "admin")),
    session: AsyncSession = Depends(get_session),
) -> MetricsResponse:
    """KPIs over the cases table (M7): automation rate, override rate, cost.
    Pure SQL aggregates — no new state, always consistent with the source rows."""
    status_rows = await session.execute(select(Case.status, func.count()).group_by(Case.status))
    cases_by_status: dict[str, int] = {row[0]: row[1] for row in status_rows}
    total_cases = sum(cases_by_status.values())

    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(Case.tokens_used), 0),
                func.coalesce(func.sum(Case.token_cost_usd), 0),
                # overridden is NULL until a human decides, so count() over the
                # column is exactly "cases with a human decision".
                func.count(Case.overridden),
                func.coalesce(func.sum(case((Case.overridden.is_(True), 1), else_=0)), 0),
            )
        )
    ).one()
    total_tokens = int(totals[0])
    total_cost = float(totals[1])
    human_decided = int(totals[2])
    overridden = int(totals[3])

    auto_approved = cases_by_status.get("auto_approved", 0)
    terminal = sum(cases_by_status.get(s, 0) for s in _TERMINAL_STATUSES)

    return MetricsResponse(
        total_cases=total_cases,
        cases_by_status=cases_by_status,
        human_queue_depth=cases_by_status.get("human_queue", 0),
        automation_rate=auto_approved / terminal if terminal else None,
        override_rate=overridden / human_decided if human_decided else None,
        human_decided_cases=human_decided,
        overridden_cases=overridden,
        total_tokens=total_tokens,
        total_token_cost_usd=total_cost,
        avg_tokens_per_case=total_tokens / total_cases if total_cases else None,
        avg_cost_per_case_usd=total_cost / total_cases if total_cases else None,
    )
