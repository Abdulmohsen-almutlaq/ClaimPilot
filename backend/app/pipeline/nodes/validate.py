from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.pipeline.schemas import ClaimFields, ValidationResult
from app.pipeline.state import CaseState
from app.tools import crm
from app.tools.crm import CRMNotFoundError, CRMUnavailableError

_DOMAIN_CONFIG_PATH = Path(__file__).resolve().parents[4] / "configs" / "domain.claims.yaml"


@lru_cache
def _load_domain_config() -> dict[str, Any]:
    return yaml.safe_load(_DOMAIN_CONFIG_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


async def run_validate(state: CaseState) -> dict[str, Any]:
    fields = ClaimFields.model_validate(state.get("extracted_fields") or {})
    domain = _load_domain_config()
    reasons: list[str] = []

    for field_name in domain["required_fields"]:
        if getattr(fields, field_name, None) in (None, ""):
            reasons.append(f"missing required field: {field_name}")

    if fields.claimed_amount is not None:
        limits = domain["amount_limits"]
        if fields.claimed_amount < limits["min"] or fields.claimed_amount > limits["max"]:
            reasons.append(f"claimed amount {fields.claimed_amount} outside allowed range")

    if fields.category is not None and fields.category not in domain["allowed_categories"]:
        reasons.append(f"unsupported category: {fields.category}")

    policy_status: str | None = None
    if fields.policy_number:
        try:
            policy = await crm.lookup_policy(fields.policy_number)
        except CRMNotFoundError:
            reasons.append(f"policy {fields.policy_number} not found")
        except CRMUnavailableError:
            reasons.append("policy lookup unavailable")
        else:
            policy_status = policy.get("status")
            if policy_status != "active":
                reasons.append(f"policy is {policy_status}, not active")
            if fields.category and policy.get("category") != fields.category:
                reasons.append("policy does not cover claimed category")

    validation_result = ValidationResult(
        valid=not reasons, reasons=reasons, policy_status=policy_status
    )

    return {
        "validation_result": validation_result.model_dump(mode="json"),
        "status": "validated" if validation_result.valid else "needs_info",
    }
