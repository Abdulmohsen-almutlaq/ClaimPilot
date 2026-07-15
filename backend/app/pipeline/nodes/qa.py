import json
from typing import Any

from app.llm.client import LLMClient
from app.llm.registry import load_prompt
from app.pipeline.schemas import QAResult
from app.pipeline.state import CaseState

PROMPT_NAME = "qa_review"

# One regenerate cycle per spec 5.1: draft -> qa -> (regen) draft -> qa -> route.
MAX_QA_ATTEMPTS = 2


def _build_user_prompt(state: CaseState) -> str:
    evidence = state.get("evidence") or []
    evidence_text = (
        "\n".join(f"- [{e['clause_id']}] {e['text']}" for e in evidence)
        or "(no evidence retrieved)"
    )
    return (
        "<claim_fields>\n"
        f"{json.dumps(state.get('extracted_fields') or {})}\n"
        "</claim_fields>\n"
        "<validation_result>\n"
        f"{json.dumps(state.get('validation_result') or {})}\n"
        "</validation_result>\n"
        "<evidence>\n"
        f"{evidence_text}\n"
        "</evidence>\n"
        "<draft>\n"
        f"{json.dumps(state.get('draft') or {})}\n"
        "</draft>"
    )


async def run_qa(state: CaseState, *, llm_client: LLMClient) -> dict[str, Any]:
    prompt_version = llm_client.models_config.prompt_version(PROMPT_NAME)
    system_prompt = load_prompt(PROMPT_NAME, prompt_version)

    result = await llm_client.generate_structured(
        node="qa",
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt=_build_user_prompt(state),
        schema=QAResult,
        tokens_used=state.get("tokens_used", 0),
    )

    qa = result.data
    # Principle 1: never trust the model's own aggregate — recompute it.
    passed = (
        qa.claims_supported
        and qa.citations_relevant
        and qa.decision_consistent
        and qa.professional_tone
    )
    qa_result = qa.model_copy(update={"passed": passed})
    attempts = state.get("qa_attempts", 0) + 1

    return {
        "qa_result": qa_result.model_dump(mode="json"),
        "qa_attempts": attempts,
        "status": "qa_passed" if passed else "qa_failed",
        "model_versions": {**state.get("model_versions", {}), "qa": result.model_used},
        "prompt_versions": {**state.get("prompt_versions", {}), "qa": prompt_version},
        "token_cost_usd": state.get("token_cost_usd", 0.0) + float(result.cost_usd),
        "tokens_used": state.get("tokens_used", 0) + result.input_tokens + result.output_tokens,
    }
