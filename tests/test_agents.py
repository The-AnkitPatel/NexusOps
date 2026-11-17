"""Supervisor routing, end-to-end orchestration, and guardrail masking."""

from __future__ import annotations

import pytest

from nexus.agents.guardrail import guardrail_agent
from nexus.agents.supervisor import supervisor_agent


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Show incident tickets for Apollo", "SQL_QUERY"),
        ("What is the PII masking standard under POL-SEC-002?", "DOCUMENT_LOOKUP"),
        ("Does Apollo qualify for an SLA credit on their P1 ticket?", "HYBRID_REASONING"),
    ],
)
def test_intent_routing(query: str, expected: str) -> None:
    assert supervisor_agent._classify_intent(query) == expected


def test_guardrail_masks_pii() -> None:
    raw = "User email is ankit@google.com and phone is +1-555-019-2834"
    masked = guardrail_agent.mask_pii(raw)
    assert "ankit@google.com" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked


def test_supervisor_end_to_end() -> None:
    state = supervisor_agent.process(
        "Does Apollo Healthcare qualify for an SLA credit on their Cloud SQL P1 ticket?"
    )
    assert state.intent in ("HYBRID_REASONING", "SQL_QUERY")
    assert state.total_tokens > 0
    assert state.total_cost_usd > 0
    assert len(state.execution_trace) >= 4
    assert state.final_response
    assert state.execution_mode == "deterministic_offline"
    # Token estimates are derived from each step's real text, so they vary.
    token_counts = [step.tokens_used for step in state.execution_trace]
    assert len(set(token_counts)) > 1


def test_supervisor_document_only_path() -> None:
    state = supervisor_agent.process("Explain the enterprise PII masking policy")
    assert state.intent == "DOCUMENT_LOOKUP"
    assert state.retrieved_citations
    assert state.sql_results is None
