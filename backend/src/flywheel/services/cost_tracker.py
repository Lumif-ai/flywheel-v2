"""Token cost calculation per model.

Calculates USD cost from token usage dictionaries returned by the Anthropic SDK.
Pricing is per million tokens, sourced from Anthropic's published pricing page.

Public API:
    calculate_cost(token_usage) -> float | None
"""

from __future__ import annotations

# Pricing per million tokens (as of March 2026)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
}

# Default to Sonnet pricing for unknown models
_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def calculate_cost(token_usage: dict | None) -> float | None:
    """Calculate cost estimate from token usage dict.

    Args:
        token_usage: Dict with 'input_tokens', 'output_tokens', 'model' keys.
            Typically returned by the Anthropic SDK's response.usage.

    Returns:
        Estimated cost in USD rounded to 4 decimal places, or None if no usage data.
    """
    if not token_usage:
        return None

    model = token_usage.get("model", _DEFAULT_MODEL)
    input_tokens = token_usage.get("input_tokens", 0)
    output_tokens = token_usage.get("output_tokens", 0)

    pricing = MODEL_PRICING.get(model, MODEL_PRICING[_DEFAULT_MODEL])
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    return round(cost, 4)
