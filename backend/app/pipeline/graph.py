from functools import partial
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from app.llm.client import LLMClient
from app.pipeline.nodes.draft import run_draft
from app.pipeline.nodes.evidence import run_evidence
from app.pipeline.nodes.intake import run_intake
from app.pipeline.nodes.qa import MAX_QA_ATTEMPTS, run_qa
from app.pipeline.nodes.route import run_route
from app.pipeline.nodes.validate import run_validate
from app.pipeline.state import CaseState
from app.rag.retrieve import Retriever


def _route_after_validate(
    state: CaseState,
) -> Literal["evidence", "needs_info", "dependency_down"]:
    if state.get("route_reason") == "dependency_down":
        return "dependency_down"
    validation = state.get("validation_result") or {}
    return "evidence" if validation.get("valid") else "needs_info"


def _route_after_evidence(state: CaseState) -> Literal["draft", "no_evidence"]:
    return "draft" if state.get("evidence") else "no_evidence"


def _route_after_qa(state: CaseState) -> Literal["route", "draft"]:
    qa = state.get("qa_result") or {}
    if qa.get("passed"):
        return "route"
    if state.get("qa_attempts", 0) < MAX_QA_ATTEMPTS:
        return "draft"  # regenerate once with the QA reviewer's feedback
    return "route"  # second failure: route decides (it will send this to a human)


async def _mark_needs_info(state: CaseState) -> dict[str, str]:
    return {"status": "needs_info"}


async def _mark_no_evidence(state: CaseState) -> dict[str, str]:
    # run_evidence already set status/route; this terminal node exists so the
    # no-evidence path is an explicit, auditable step in the graph rather than
    # an implicit early END.
    return {}


async def _mark_dependency_down(state: CaseState) -> dict[str, str]:
    # run_validate already set status/route/route_reason; explicit terminal
    # node for the same auditability reason as _mark_no_evidence.
    return {}


def build_graph(
    llm_client: LLMClient, retriever: Retriever
) -> StateGraph[CaseState, None, CaseState, CaseState]:
    graph = StateGraph(CaseState)
    graph.add_node("intake", partial(run_intake, llm_client=llm_client))
    graph.add_node("validate", run_validate)
    graph.add_node("evidence", partial(run_evidence, retriever=retriever))
    graph.add_node("draft", partial(run_draft, llm_client=llm_client))
    graph.add_node("qa", partial(run_qa, llm_client=llm_client))
    graph.add_node("route", run_route)
    graph.add_node("needs_info", _mark_needs_info)
    graph.add_node("no_evidence", _mark_no_evidence)
    graph.add_node("dependency_down", _mark_dependency_down)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "validate")
    graph.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "evidence": "evidence",
            "needs_info": "needs_info",
            "dependency_down": "dependency_down",
        },
    )
    graph.add_conditional_edges(
        "evidence", _route_after_evidence, {"draft": "draft", "no_evidence": "no_evidence"}
    )
    graph.add_edge("draft", "qa")
    graph.add_conditional_edges("qa", _route_after_qa, {"route": "route", "draft": "draft"})
    graph.add_edge("route", END)
    graph.add_edge("needs_info", END)
    graph.add_edge("no_evidence", END)
    graph.add_edge("dependency_down", END)

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
