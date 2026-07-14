from decimal import Decimal

from app.llm.pricing import estimate_cost_usd


def test_known_model_cost_is_positive() -> None:
    cost = estimate_cost_usd("claude-sonnet-4-6", 1000, 500)
    assert cost > Decimal("0")


def test_unknown_model_costs_zero() -> None:
    cost = estimate_cost_usd("some-local-model", 100_000, 100_000)
    assert cost == Decimal("0")


def test_zero_tokens_cost_zero() -> None:
    cost = estimate_cost_usd("claude-sonnet-4-6", 0, 0)
    assert cost == Decimal("0")
