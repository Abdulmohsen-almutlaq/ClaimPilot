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
    passed: bool
    reasons: list[str] = Field(default_factory=list)
