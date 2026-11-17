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
