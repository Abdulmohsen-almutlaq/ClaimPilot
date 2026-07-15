from functools import partial
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from app.llm.client import LLMClient
from app.pipeline.nodes.draft import run_draft
from app.pipeline.nodes.evidence import run_evidence
from app.pipeline.nodes.intake import run_intake
from app.pipeline.nodes.validate import run_validate
from app.pipeline.state import CaseState
from app.rag.retrieve import Retriever


def _route_after_validate(state: CaseState) -> Literal["evidence", "needs_info"]:
    validation = state.get("validation_result") or {}
    return "evidence" if validation.get("valid") else "needs_info"


def _route_after_evidence(state: CaseState) -> Literal["draft", "no_evidence"]:
    return "draft" if state.get("evidence") else "no_evidence"


async def _mark_needs_info(state: CaseState) -> dict[str, str]:
    return {"status": "needs_info"}


async def _mark_no_evidence(state: CaseState) -> dict[str, str]:
    # run_evidence already set status/route; this terminal node exists so the
    # no-evidence path is an explicit, auditable step in the graph rather than
    # an implicit early END.
    return {}


def build_graph(
    llm_client: LLMClient, retriever: Retriever
) -> StateGraph[CaseState, None, CaseState, CaseState]:
    graph = StateGraph(CaseState)
    graph.add_node("intake", partial(run_intake, llm_client=llm_client))
    graph.add_node("validate", run_validate)
    graph.add_node("evidence", partial(run_evidence, retriever=retriever))
    graph.add_node("draft", partial(run_draft, llm_client=llm_client))
    graph.add_node("needs_info", _mark_needs_info)
    graph.add_node("no_evidence", _mark_no_evidence)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "validate")
    graph.add_conditional_edges(
        "validate", _route_after_validate, {"evidence": "evidence", "needs_info": "needs_info"}
    )
    graph.add_conditional_edges(
        "evidence", _route_after_evidence, {"draft": "draft", "no_evidence": "no_evidence"}
    )
    graph.add_edge("draft", END)
    graph.add_edge("needs_info", END)
    graph.add_edge("no_evidence", END)

    return graph


def compile_graph(
    llm_client: LLMClient,
    retriever: Retriever,
    checkpointer: Checkpointer,
    **compile_kwargs: Any,
) -> CompiledStateGraph[CaseState, None, CaseState, CaseState]:
    return build_graph(llm_client, retriever).compile(
        checkpointer=checkpointer, **compile_kwargs
    )
