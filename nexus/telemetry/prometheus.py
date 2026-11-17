"""Prometheus metrics for the HTTP layer."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "nexus_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "nexus_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)


def observe(method: str, path: str, status: int, duration_s: float) -> None:
    REQUEST_COUNT.labels(method, path, str(status)).inc()
    REQUEST_LATENCY.labels(method, path).observe(duration_s)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
