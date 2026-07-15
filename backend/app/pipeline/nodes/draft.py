from typing import Any

from app.llm.client import LLMClient
from app.llm.registry import load_prompt
from app.pipeline.schemas import ClaimFields, DecisionDraft, QAResult, ValidationResult
from app.pipeline.state import CaseState

PROMPT_NAME = "draft_decision"


def _qa_feedback_block(state: CaseState) -> str:
    """When the QA reviewer failed the previous draft, its actionable reasons are
    fed back verbatim for exactly one revision (spec 5.1's regenerate loop)."""
    raw = state.get("qa_result")
    if not raw or not state.get("qa_attempts"):
        return ""
    qa = QAResult.model_validate(raw)
    if qa.passed or not qa.reasons:
        return ""
    reasons = "\n".join(f"- {reason}" for reason in qa.reasons)
    return (
        "\n<qa_feedback>\n"
        "A quality reviewer rejected your previous draft for these reasons. "
        "Revise the draft to address every one of them:\n"
        f"{reasons}\n"
        "</qa_feedback>"
    )


def _build_user_prompt(
    fields: ClaimFields,
    validation: ValidationResult,
    evidence: list[dict[str, Any]],
    feedback_block: str,
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
        f"{feedback_block}"
    )


async def run_draft(state: CaseState, *, llm_client: LLMClient) -> dict[str, Any]:
    fields = ClaimFields.model_validate(state.get("extracted_fields") or {})
    validation = ValidationResult.model_validate(
        state.get("validation_result") or {"valid": False}
    )
    evidence = state.get("evidence") or []

    prompt_version = llm_client.models_config.prompt_version(PROMPT_NAME)
    system_prompt = load_prompt(PROMPT_NAME, prompt_version)
    user_prompt = _build_user_prompt(fields, validation, evidence, _qa_feedback_block(state))

    result = await llm_client.generate_structured(
        node="draft",
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=DecisionDraft,
        tokens_used=state.get("tokens_used", 0),
    )

    return {
        "draft": result.data.model_dump(mode="json"),
        "status": "drafted",
        "model_versions": {**state.get("model_versions", {}), "draft": result.model_used},
        "prompt_versions": {**state.get("prompt_versions", {}), "draft": prompt_version},
        "token_cost_usd": state.get("token_cost_usd", 0.0) + float(result.cost_usd),
        "tokens_used": state.get("tokens_used", 0) + result.input_tokens + result.output_tokens,
    }
