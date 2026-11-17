"""Pydantic state objects threaded through the multi-agent pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    section_title: str
    snippet: str
    relevance_score: float  # fused RRF score (scaled), higher = more relevant
    bm25_score: float = 0.0  # raw Okapi BM25 sparse score
    dense_score: float = 0.0  # TF-IDF cosine similarity (0..1)


class AgentStepTrace(BaseModel):
    agent_name: str
    action: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    duration_ms: float
    tokens_used: int = 0  # estimated (see cost_calculator.estimate_tokens)
    estimated_cost_usd: float = 0.0


class NexusState(BaseModel):
    session_id: str
    user_query: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Routing & intent
    intent: str | None = None  # DOCUMENT_LOOKUP | SQL_QUERY | HYBRID_REASONING
    execution_mode: str = "deterministic_offline"  # or "live_gemini"

    # Retrieved & structured context
    retrieved_citations: list[Citation] = Field(default_factory=list)
    sql_query: str | None = None
    sql_results: list[dict[str, Any]] | None = None

    # Generation & evaluation
    draft_response: str | None = None
    final_response: str | None = None
    hallucination_detected: bool = False
    groundedness_score: float = 1.0  # 0.0 .. 1.0 (token-overlap grounding proxy)
    guardrail_status: str = "PENDING"  # PASSED | FLAGGED

    # Telemetry (estimated token accounting in offline mode)
    execution_trace: list[AgentStepTrace] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
