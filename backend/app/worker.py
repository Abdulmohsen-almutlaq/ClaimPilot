import uuid
from decimal import Decimal
from typing import Any

from arq.connections import ArqRedis, RedisSettings, create_pool
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.db.session import session_factory
from app.llm.client import LLMClient
from app.models.case import Case
from app.pipeline.checkpointer import get_checkpointer
from app.pipeline.graph import compile_graph
from app.pipeline.state import CaseState

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if get_settings().app_env == "test":
        # Tests mix pytest-asyncio's loop with TestClient's own internal loop per
        # call; a cached pool can outlive the loop it was opened on (same class of
        # issue as the SQLAlchemy NullPool-under-test fix in app/db/session.py).
        return await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue_case_pipeline(case_id: str) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("run_case_pipeline", case_id)


async def run_case_pipeline(
    _ctx: dict[str, Any], case_id: str, *, llm_client: LLMClient | None = None
) -> None:
    case_uuid = uuid.UUID(case_id)

    async with session_factory() as session:
        case = await session.get(Case, case_uuid)
        if case is None:
            return
        initial_state: CaseState = {
            "case_id": str(case.id),
            "document_hash": case.document_hash,
            "document_text": case.document_text or "",
            "status": case.status,
            "extracted_fields": case.extracted_fields,
            "validation_result": case.validation_result,
            "evidence": case.evidence or [],
            "draft": case.draft,
            "model_versions": case.model_versions or {},
            "prompt_versions": case.prompt_versions or {},
            "token_cost_usd": float(case.token_cost_usd),
            "errors": [],
        }

    llm_client = llm_client or LLMClient()
    config: RunnableConfig = {"configurable": {"thread_id": case_id}}
    try:
        async with get_checkpointer() as checkpointer:
            graph = compile_graph(llm_client, checkpointer)
            final_state = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        async with session_factory() as session:
            case = await session.get(Case, case_uuid)
            if case is not None:
                case.status = "error"
                case.errors = [str(exc)]
                await session.commit()
        raise

    async with session_factory() as session:
        case = await session.get(Case, case_uuid)
        if case is None:
            return
        case.status = final_state.get("status", case.status)
        case.extracted_fields = final_state.get("extracted_fields")
        case.validation_result = final_state.get("validation_result")
        case.evidence = final_state.get("evidence")
        case.draft = final_state.get("draft")
        case.model_versions = final_state.get("model_versions")
        case.prompt_versions = final_state.get("prompt_versions")
        case.token_cost_usd = Decimal(str(final_state.get("token_cost_usd", 0)))
        await session.commit()


class WorkerSettings:
    functions = [run_case_pipeline]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
