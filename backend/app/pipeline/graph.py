from functools import partial
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from app.llm.client import LLMClient
from app.pipeline.nodes.draft import run_draft
from app.pipeline.nodes.intake import run_intake
from app.pipeline.nodes.validate import run_validate
from app.pipeline.state import CaseState


def _route_after_validate(state: CaseState) -> Literal["draft", "needs_info"]:
    validation = state.get("validation_result") or {}
    return "draft" if validation.get("valid") else "needs_info"


async def _mark_needs_info(state: CaseState) -> dict[str, str]:
    return {"status": "needs_info"}


def build_graph(llm_client: LLMClient) -> StateGraph[CaseState, None, CaseState, CaseState]:
    graph = StateGraph(CaseState)
    graph.add_node("intake", partial(run_intake, llm_client=llm_client))
    graph.add_node("validate", run_validate)
    graph.add_node("draft", partial(run_draft, llm_client=llm_client))
    graph.add_node("needs_info", _mark_needs_info)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "validate")
    graph.add_conditional_edges(
        "validate", _route_after_validate, {"draft": "draft", "needs_info": "needs_info"}
    )
    graph.add_edge("draft", END)
    graph.add_edge("needs_info", END)

    return graph


def compile_graph(
    llm_client: LLMClient, checkpointer: Checkpointer, **compile_kwargs: Any
) -> CompiledStateGraph[CaseState, None, CaseState, CaseState]:
    return build_graph(llm_client).compile(checkpointer=checkpointer, **compile_kwargs)
