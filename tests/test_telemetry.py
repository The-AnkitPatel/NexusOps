"""Token estimation, cost accounting, metrics, and OTel span emission."""

from __future__ import annotations

from nexus.telemetry.cost_calculator import calculate_token_cost, estimate_tokens
from nexus.telemetry.metrics import metrics_collector
from nexus.telemetry.tracer import get_captured_spans, otlp_enabled, record_genai_span


def test_estimate_tokens_is_chars_div_4() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 9) == 3  # ceil(9/4)


def test_cost_calculation() -> None:
    # 10k input ($0.075/1M) + 2k output ($0.30/1M) = 0.00075 + 0.00060
    assert calculate_token_cost(10000, 2000) == 0.00135


def test_otlp_disabled_without_endpoint() -> None:
    assert otlp_enabled is False


def test_genai_span_follows_semconv() -> None:
    record_genai_span(
        operation_name="unit_test_op",
        model_name="gemini-2.5-flash",
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.0001,
        attributes={"nexus.intent": "UNIT"},
    )
    spans = [s for s in get_captured_spans() if s.name == "gen_ai.unit_test_op"]
    assert spans
    attrs = spans[-1].attributes or {}
    assert attrs["gen_ai.system"] == "gemini"
    assert attrs["gen_ai.usage.input_tokens"] == 10
    assert attrs["gen_ai.usage.total_tokens"] == 15
    assert attrs["nexus.intent"] == "UNIT"


def test_metrics_collector_percentiles() -> None:
    metrics_collector.record_query(
        latency_ms=120.5,
        tokens=350,
        cost_usd=0.00012,
        violated_guardrail=False,
        trace_summary={"test": True},
    )
    summary = metrics_collector.get_metrics_summary()
    assert summary["total_queries"] > 0
    assert summary["p95_latency_ms"] > 0
    assert summary["total_tokens_consumed"] >= 350
