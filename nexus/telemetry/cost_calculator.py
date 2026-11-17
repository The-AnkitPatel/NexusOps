"""Token estimation and USD cost accounting.

No live LLM call is made in offline mode, so there is no provider-returned token
count. We therefore *estimate* tokens from real text using the well-known
~4-characters-per-token heuristic and label every number as an estimate. In live
mode the provider's ``usage`` metadata would replace :func:`estimate_tokens`.
"""

from __future__ import annotations

import math

from nexus.config import settings

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count for ``text`` (~4 chars/token). Always >= 1 for input."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))


def calculate_token_cost(input_tokens: int, output_tokens: int) -> float:
    """Cost in USD for the given token counts at the configured model pricing.

    Default: Gemini 2.5 Flash ($0.075 / 1M input, $0.30 / 1M output).
    """
    input_cost = (input_tokens / 1_000_000.0) * settings.COST_PER_MILLION_INPUT
    output_cost = (output_tokens / 1_000_000.0) * settings.COST_PER_MILLION_OUTPUT
    return round(input_cost + output_cost, 6)
