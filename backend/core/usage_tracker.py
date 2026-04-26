from pydantic import BaseModel
from pydantic_ai.usage import RunUsage

# Prices in USD per 1M tokens (input, output)
# Source: provider pricing pages as of 2025-04
_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o":                        (2.50,  10.00),
    "gpt-4o-mini":                   (0.15,   0.60),
    "gpt-4-turbo":                  (10.00,  30.00),
    "gpt-4":                        (30.00,  60.00),
    "gpt-3.5-turbo":                 (0.50,   1.50),
    # Anthropic
    "claude-opus-4":                (15.00,  75.00),
    "claude-sonnet-4":               (3.00,  15.00),
    "claude-haiku-4":                (0.80,   4.00),
    "claude-3-5-sonnet":             (3.00,  15.00),
    "claude-3-5-haiku":              (0.80,   4.00),
    "claude-3-opus":                (15.00,  75.00),
    "claude-3-haiku":                (0.25,   1.25),
    # Google
    "gemini-2.0-flash":              (0.10,   0.40),
    "gemini-2.0-flash-lite":         (0.075,  0.30),
    "gemini-1.5-pro":                (1.25,   5.00),
    "gemini-1.5-flash":              (0.075,  0.30),
}


class UsageSummary(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_display: str  # e.g. "$0.0023"
    pricing_known: bool


def compute_cost(model: str, usage: RunUsage) -> UsageSummary:
    input_tokens = usage.request_tokens or 0
    output_tokens = usage.response_tokens or 0
    total_tokens = usage.total_tokens or (input_tokens + output_tokens)

    # Match by longest prefix so "claude-3-5-sonnet-20241022" hits "claude-3-5-sonnet"
    input_price, output_price, pricing_known = 0.0, 0.0, False
    for key in sorted(_PRICING, key=len, reverse=True):
        if model.startswith(key):
            input_price, output_price = _PRICING[key]
            pricing_known = True
            break

    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price

    return UsageSummary(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=round(cost, 6),
        cost_display=f"${cost:.4f}" if cost >= 0.0001 else f"${cost:.6f}",
        pricing_known=pricing_known,
    )
