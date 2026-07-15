import uuid
from decimal import Decimal
from typing import Any

from arq.connections import ArqRedis, RedisSettings, create_pool
from langchain_core.runnables import RunnableConfig

from app.audit.writer import write_audit_event
from app.config import get_settings
from app.db.session import session_factory
from app.llm.client import LLMClient
from app.models.case import Case
from app.pipeline.checkpointer import get_checkpointer
from app.pipeline.graph import compile_graph
from app.pipeline.state import CaseState
from app.rag.retrieve import Retriever, build_default_retriever

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


async def _audit(case_id: uuid.UUID, event_type: str, **kwargs: Any) -> None:
    async with session_factory() as session:
        await write_audit_event(
            session, case_id=case_id, actor="pipeline", event_type=event_type, **kwargs
        )


async def _audit_node_update(
    case_id: uuid.UUID, node: str, update: dict[str, Any], cost_delta: float | None
) -> None:
    model_versions = update.get("model_versions") or {}
    prompt_versions = update.get("prompt_versions") or {}
    await _audit(
        case_id,
        "node_completed",
        node=node,
        model=model_versions.get(node),
        prompt_version=prompt_versions.get(node),
        payload={"status": update.get("status"), "updated": sorted(update)},
        cost_usd=Decimal(str(cost_delta)) if cost_delta else None,
    )


async def run_case_pipeline(
    _ctx: dict[str, Any],
    case_id: str,
    *,
    llm_client: LLMClient | None = None,
    retriever: Retriever | None = None,
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
    retriever = retriever or build_default_retriever()
    config: RunnableConfig = {"configurable": {"thread_id": case_id}}

    await _audit(
        case_uuid,
        "pipeline_started",
        input_hash=initial_state.get("document_hash"),
        payload={"status": initial_state.get("status")},
    )

    try:
        async with get_checkpointer() as checkpointer:
            graph = compile_graph(llm_client, retriever, checkpointer)
            # Streaming per-node updates (rather than one ainvoke) is what lets
            # every node completion land in the append-only audit trail.
            running_cost = initial_state.get("token_cost_usd", 0.0)
            async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
                for node, update in chunk.items():
                    if node.startswith("__") or update is None:
                        continue
                    new_cost = update.get("token_cost_usd")
                    cost_delta = new_cost - running_cost if new_cost is not None else None
                    running_cost = new_cost if new_cost is not None else running_cost
                    await _audit_node_update(case_uuid, node, update, cost_delta)
            snapshot = await graph.aget_state(config)
            final_state = snapshot.values
    except Exception as exc:
        await _audit(case_uuid, "pipeline_failed", payload={"error": str(exc)})
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
        case.route = final_state.get("route")
        case.extracted_fields = final_state.get("extracted_fields")
        case.validation_result = final_state.get("validation_result")
        case.evidence = final_state.get("evidence")
        case.draft = final_state.get("draft")
        case.model_versions = final_state.get("model_versions")
        case.prompt_versions = final_state.get("prompt_versions")
        case.token_cost_usd = Decimal(str(final_state.get("token_cost_usd", 0)))
        await session.commit()

    await _audit(
        case_uuid,
        "pipeline_completed",
        payload={"status": final_state.get("status"), "route": final_state.get("route")},
    )


class WorkerSettings:
    functions = [run_case_pipeline]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
