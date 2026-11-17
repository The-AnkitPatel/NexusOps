from nexus.config import settings

def calculate_token_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Calculates cost in USD according to model pricing.
    Default: Gemini 2.5 Flash ($0.075 / 1M input, $0.30 / 1M output).
    """
    input_cost = (input_tokens / 1_000_000.0) * settings.COST_PER_MILLION_INPUT
    output_cost = (output_tokens / 1_000_000.0) * settings.COST_PER_MILLION_OUTPUT
    return round(input_cost + output_cost, 6)
