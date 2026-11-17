import pytest
from nexus.agents.supervisor import supervisor_agent
from nexus.agents.sql_agent import sql_agent
from nexus.agents.guardrail import guardrail_agent

def test_sql_agent_execution():
    sql, rows, dur = sql_agent.execute_query("Show tickets for Apollo Global Healthcare")
    assert "ACC-101" in sql
    assert len(rows) > 0
    assert dur > 0

def test_sql_agent_security_blocks_drop():
    with pytest.raises(ValueError):
        sql_agent._generate_sql("DROP TABLE accounts")
        sql_agent.execute_query("DROP TABLE accounts")

def test_guardrail_masks_pii():
    raw = "User email is ankit@google.com and phone is +1-555-019-2834"
    masked = guardrail_agent.mask_pii(raw)
    assert "ankit@google.com" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked

def test_supervisor_end_to_end():
    query = "Does Apollo Healthcare qualify for an SLA credit on their Cloud SQL P1 ticket?"
    state = supervisor_agent.process(query)
    
    assert state.intent in ["HYBRID_REASONING", "SQL_QUERY"]
    assert state.total_tokens > 0
    assert state.total_cost_usd > 0
    assert len(state.execution_trace) >= 3
    assert state.final_response is not None
