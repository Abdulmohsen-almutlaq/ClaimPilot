"""Boundary normalization of LLM output (principle 1). Both bugs here were found
by the eval harness against the live model: string "null" fields passing
validation, and formatted money breaking Decimal parsing."""

from decimal import Decimal

from app.pipeline.schemas import ClaimFields, DecisionDraft


def test_string_null_sentinels_become_none() -> None:
    fields = ClaimFields.model_validate(
        {
            "claimant_name": "null",
            "policy_number": "N/A",
            "incident_date": "unknown",
            "claimed_amount": "none",
            "category": "Not Provided",
            "description": "",
        }
    )
    assert fields.claimant_name is None
    assert fields.policy_number is None
    assert fields.incident_date is None
    assert fields.claimed_amount is None
    assert fields.category is None
    assert fields.description is None


def test_real_values_pass_through_unchanged() -> None:
    fields = ClaimFields.model_validate(
        {
            "claimant_name": "Ava Thompson",
            "policy_number": "POL-AUTO-001",
            "incident_date": "2026-06-20",
            "claimed_amount": "1200.00",
            "category": "auto",
        }
    )
    assert fields.claimant_name == "Ava Thompson"
    assert fields.claimed_amount == Decimal("1200.00")


def test_formatted_money_is_normalized() -> None:
    fields = ClaimFields.model_validate({"claimed_amount": "$1,850.00"})
    assert fields.claimed_amount == Decimal("1850.00")
    fields = ClaimFields.model_validate({"claimed_amount": "17,500 USD"})
    assert fields.claimed_amount == Decimal("17500")


def test_draft_payout_money_is_normalized() -> None:
    draft = DecisionDraft.model_validate(
        {
            "decision": "approve",
            "payout_amount": "$17,500.00",
            "reasoning": "covered",
            "confidence": 0.9,
        }
    )
    assert draft.payout_amount == Decimal("17500.00")
