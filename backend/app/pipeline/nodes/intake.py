from typing import Any

from app.llm.client import LLMClient
from app.llm.registry import load_prompt
from app.pipeline.schemas import ClaimFields
from app.pipeline.state import CaseState

PROMPT_NAME = "intake_extract"


async def run_intake(state: CaseState, *, llm_client: LLMClient) -> dict[str, Any]:
    document_text = state["document_text"]
    prompt_version = llm_client.models_config.prompt_version(PROMPT_NAME)
    system_prompt = load_prompt(PROMPT_NAME, prompt_version)
    user_prompt = f"<document>\n{document_text}\n</document>"

    result = await llm_client.generate_structured(
        node="intake",
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=ClaimFields,
    )

    return {
        "extracted_fields": result.data.model_dump(mode="json"),
        "status": "validating",
        "model_versions": {**state.get("model_versions", {}), "intake": result.model_used},
        "prompt_versions": {**state.get("prompt_versions", {}), "intake": prompt_version},
        "token_cost_usd": state.get("token_cost_usd", 0.0) + float(result.cost_usd),
        "tokens_used": state.get("tokens_used", 0) + result.input_tokens + result.output_tokens,
    }
