"""In-memory telemetry aggregation: latency percentiles, tokens, cost."""

from __future__ import annotations

from typing import Any

import numpy as np


class TelemetryCollector:
    def __init__(self) -> None:
        self.latencies_ms: list[float] = []
        self.token_counts: list[int] = []
        self.costs_usd: list[float] = []
        self.total_queries: int = 0
        self.guardrail_violations: int = 0
        self.traces: list[dict[str, Any]] = []

    def record_query(
        self,
        latency_ms: float,
        tokens: int,
        cost_usd: float,
        violated_guardrail: bool,
        trace_summary: dict[str, Any],
    ) -> None:
        self.total_queries += 1
        self.latencies_ms.append(latency_ms)
        self.token_counts.append(tokens)
        self.costs_usd.append(cost_usd)
        if violated_guardrail:
            self.guardrail_violations += 1
        self.traces.append(trace_summary)
        if len(self.traces) > 200:
            self.traces.pop(0)

    def get_metrics_summary(self) -> dict[str, Any]:
        if not self.latencies_ms:
            return {
                "total_queries": 0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "total_tokens_consumed": 0,
                "total_cost_usd": 0.0,
                "guardrail_intercept_rate": "0.0%",
            }
        rate = (self.guardrail_violations / max(1, self.total_queries)) * 100
        return {
            "total_queries": self.total_queries,
            "p50_latency_ms": round(float(np.percentile(self.latencies_ms, 50)), 2),
            "p95_latency_ms": round(float(np.percentile(self.latencies_ms, 95)), 2),
            "p99_latency_ms": round(float(np.percentile(self.latencies_ms, 99)), 2),
            "total_tokens_consumed": sum(self.token_counts),
            "total_cost_usd": round(sum(self.costs_usd), 6),
            "guardrail_intercept_rate": f"{round(rate, 2)}%",
        }


metrics_collector = TelemetryCollector()
