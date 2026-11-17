"""FastAPI gateway contract tests via Starlette's TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nexus.api.server import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "HEALTHY"
    assert body["execution_mode"] in ("deterministic_offline", "live_gemini")
    assert body["otlp_export_enabled"] is False


def test_agent_query_returns_state() -> None:
    resp = client.post(
        "/v1/agent/query",
        json={"query": "List all P0/P1 incidents across accounts and total downtime"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in ("SQL_QUERY", "HYBRID_REASONING")
    assert data["total_tokens"] > 0
    assert data["final_response"]


def test_empty_query_rejected() -> None:
    resp = client.post("/v1/agent/query", json={"query": "   "})
    assert resp.status_code == 400


def test_metrics_endpoint_populates() -> None:
    client.post("/v1/agent/query", json={"query": "PII masking standard POL-SEC-002"})
    resp = client.get("/v1/telemetry/metrics")
    assert resp.status_code == 200
    assert resp.json()["total_queries"] >= 1


def test_stream_endpoint_emits_sse_events() -> None:
    resp = client.post(
        "/v1/agent/query/stream",
        json={"query": "List all P0/P1 incidents across accounts and total downtime"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "event: step" in body
    assert "event: final" in body
    assert "event: done" in body


def test_request_id_and_security_headers() -> None:
    resp = client.get("/v1/health")
    assert resp.headers.get("X-Request-ID")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_liveness_and_readiness_probes() -> None:
    assert client.get("/livez").json() == {"status": "alive"}
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_prometheus_metrics_endpoint() -> None:
    client.get("/v1/health")  # generate at least one request sample
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "nexus_http_requests_total" in resp.text


def test_oversized_query_rejected() -> None:
    resp = client.post("/v1/agent/query", json={"query": "x" * 5000})
    assert resp.status_code == 422


def test_guardrail_error_returns_400_envelope() -> None:
    resp = client.post("/v1/agent/query", json={"query": "DROP TABLE accounts"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "guardrail_blocked"
