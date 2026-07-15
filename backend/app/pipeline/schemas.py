from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ClaimFields(BaseModel):
    claimant_name: str | None = None
    policy_number: str | None = None
    incident_date: date | None = None
    claimed_amount: Decimal | None = None
    category: str | None = None
    description: str | None = None


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
