from typing import Any, TypedDict


class CaseState(TypedDict, total=False):
    case_id: str
    document_hash: str
    document_text: str
    status: str
    extracted_fields: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    draft: dict[str, Any] | None
    qa_result: dict[str, Any] | None
    qa_attempts: int
    route: str | None
    route_reason: str | None
    errors: list[str]
    token_cost_usd: float
    tokens_used: int
    model_versions: dict[str, str]
    prompt_versions: dict[str, str]
