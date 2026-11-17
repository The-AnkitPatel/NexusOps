import pytest
from nexus.telemetry.cost_calculator import calculate_token_cost
from nexus.telemetry.metrics import metrics_collector
from nexus.agents.supervisor import supervisor_agent

def test_cost_calculation():
    # 10,000 prompt tokens ($0.075/1M) + 2,000 completion tokens ($0.30/1M)
    # = 0.00075 + 0.00060 = 0.00135 USD
    cost = calculate_token_cost(10000, 2000)
    assert cost == 0.00135

def test_metrics_collector():
    metrics_collector.record_query(
        latency_ms=120.5,
        tokens=350,
        cost_usd=0.00012,
        violated_guardrail=False,
        trace_summary={"test": True}
    )
    summary = metrics_collector.get_metrics_summary()
    assert summary["total_queries"] > 0
    assert summary["p95_latency_ms"] > 0
    assert summary["total_tokens_consumed"] >= 350
