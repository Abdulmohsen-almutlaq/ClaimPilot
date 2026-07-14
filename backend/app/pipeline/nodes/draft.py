from typing import Any

from app.llm.client import LLMClient
from app.llm.registry import load_prompt
from app.pipeline.schemas import ClaimFields, DecisionDraft, ValidationResult
from app.pipeline.state import CaseState

PROMPT_NAME = "draft_decision"


def _build_user_prompt(
    fields: ClaimFields, validation: ValidationResult, evidence: list[dict[str, Any]]
) -> str:
    evidence_text = (
        "\n".join(f"- [{e['clause_id']}] {e['text']}" for e in evidence)
        or "(no evidence retrieved)"
    )
    return (
        "<claim_fields>\n"
        f"{fields.model_dump_json()}\n"
        "</claim_fields>\n"
        "<validation_result>\n"
        f"{validation.model_dump_json()}\n"
        "</validation_result>\n"
        "<evidence>\n"
        f"{evidence_text}\n"
        "</evidence>"
    )


async def run_draft(state: CaseState, *, llm_client: LLMClient) -> dict[str, Any]:
    fields = ClaimFields.model_validate(state.get("extracted_fields") or {})
    validation = ValidationResult.model_validate(
        state.get("validation_result") or {"valid": False}
    )
    evidence = state.get("evidence") or []

    prompt_version = llm_client.models_config.prompt_version(PROMPT_NAME)
    system_prompt = load_prompt(PROMPT_NAME, prompt_version)
    user_prompt = _build_user_prompt(fields, validation, evidence)

    result = await llm_client.generate_structured(
        node="draft",
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=DecisionDraft,
    )

    return {
        "draft": result.data.model_dump(mode="json"),
        "status": "drafted",
        "model_versions": {**state.get("model_versions", {}), "draft": result.model_used},
        "prompt_versions": {**state.get("prompt_versions", {}), "draft": prompt_version},
        "token_cost_usd": state.get("token_cost_usd", 0.0) + float(result.cost_usd),
    }
