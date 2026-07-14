from decimal import Decimal

# USD per 1M tokens (input, output). Approximate list pricing — update alongside
# configs/models.yaml when model choices change. Unlisted models (e.g. self-hosted
# local models) cost $0 in USD terms.
_PRICING_PER_MILLION: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-haiku-4-5-20251001": (Decimal("0.80"), Decimal("4.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
}
_ZERO_PRICE = (Decimal("0"), Decimal("0"))


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    input_price, output_price = _PRICING_PER_MILLION.get(model, _ZERO_PRICE)
    cost = (
        Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))
