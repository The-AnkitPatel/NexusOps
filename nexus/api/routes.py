"""FastAPI routes for the agent gateway and telemetry endpoints."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from nexus.agents.sql_agent import sql_agent
from nexus.agents.supervisor import supervisor_agent
from nexus.config import settings
from nexus.rag.document_store import document_store
from nexus.rag.hybrid_search import hybrid_retriever
from nexus.state import NexusState
from nexus.telemetry import prometheus
from nexus.telemetry.metrics import metrics_collector
from nexus.telemetry.tracer import otlp_enabled

router = APIRouter()

MAX_QUERY_LEN = 2000


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LEN)
    session_id: str | None = None


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/v1/agent/query", response_model=NexusState)
def execute_agent_query(req: QueryRequest) -> NexusState:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return supervisor_agent.process(req.query, session_id=req.session_id)


@router.post("/v1/agent/query/stream")
def stream_agent_query(req: QueryRequest) -> StreamingResponse:
    """Run the pipeline and stream the per-agent trace, then the final state, as SSE."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    state = supervisor_agent.process(req.query, session_id=req.session_id)

    def event_stream() -> Iterator[str]:
        for step in state.execution_trace:
            yield _sse("step", step.model_dump())
        yield _sse("final", state.model_dump(mode="json"))
        yield _sse("done", {"session_id": state.session_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/v1/telemetry/metrics")
def get_telemetry_metrics() -> dict[str, Any]:
    return metrics_collector.get_metrics_summary()


@router.get("/v1/telemetry/traces")
def get_recent_traces() -> list[dict[str, Any]]:
    return metrics_collector.traces[-50:]


@router.get("/v1/health")
def healthcheck() -> dict[str, Any]:
    return {
        "status": "HEALTHY",
        "system": "NexusOps Enterprise Gateway",
        "version": settings.SERVICE_VERSION,
        "execution_mode": supervisor_agent.execution_mode,
        "dense_embedder": hybrid_retriever.embedder.name,
        "otlp_export_enabled": otlp_enabled,
    }


@router.get("/livez")
def livez() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        sql_agent.introspect_schema()
        ready = bool(document_store.get_all()) and len(hybrid_retriever.docs) > 0
    except Exception:
        ready = False
    if not ready:
        raise HTTPException(status_code=503, detail="Dependencies not ready.")
    return {"status": "ready"}


@router.get("/metrics")
def metrics() -> Response:
    payload, content_type = prometheus.render()
    return Response(content=payload, media_type=content_type)
