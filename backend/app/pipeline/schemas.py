from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# LLMs regularly emit the STRING "null"/"unknown" instead of JSON null for absent
# values (found by the eval harness: a claim with no claimant name auto-approved
# because "null" is a truthy string). Normalizing here — at the boundary — is
# principle 1: no unvalidated LLM output crosses into the pipeline.
_MISSING_SENTINELS = {"", "null", "none", "n/a", "na", "unknown", "not provided", "not stated"}


def _none_if_sentinel(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in _MISSING_SENTINELS:
        return None
    return value


def _clean_money(value: Any) -> Any:
    """LLMs also emit formatted money ("$17,500.00", "1200 USD") that Decimal
    rejects — found as draft-node retry exhaustion in the eval run."""
    value = _none_if_sentinel(value)
    if isinstance(value, str):
        return value.replace("$", "").replace(",", "").replace("USD", "").strip() or None
    return value


class ClaimFields(BaseModel):
    claimant_name: str | None = None
    policy_number: str | None = None
    incident_date: date | None = None
    claimed_amount: Decimal | None = None
    category: str | None = None
    description: str | None = None

    @field_validator(
        "claimant_name", "policy_number", "incident_date", "category", "description", mode="before"
    )
    @classmethod
    def _clean_strings(cls, value: Any) -> Any:
        return _none_if_sentinel(value)

    @field_validator("claimed_amount", mode="before")
    @classmethod
    def _clean_amount(cls, value: Any) -> Any:
        return _clean_money(value)


class ValidationResult(BaseModel):
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    policy_status: str | None = None


class Evidence(BaseModel):
    clause_id: str
    text: str
    similarity: float


class DecisionDraft(BaseModel):
    decision: Literal["approve", "reject", "needs_info"]
    payout_amount: Decimal | None = None
    reasoning: str
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("payout_amount", mode="before")
    @classmethod
    def _clean_payout(cls, value: Any) -> Any:
        return _clean_money(value)


class QAResult(BaseModel):
    """Rubric from spec 5.1: each check is reported separately by the QA model;
    `passed` is recomputed in the qa node as the AND of the four checks — the
    model's own aggregate is never trusted (principle 1)."""

    passed: bool
    claims_supported: bool
    citations_relevant: bool
    decision_consistent: bool
    professional_tone: bool
    reasons: list[str] = Field(default_factory=list)
