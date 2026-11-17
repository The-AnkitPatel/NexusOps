"""Read-only SQL planner: guardrails, engine-level protection, introspection."""

from __future__ import annotations

import sqlite3

import pytest

from nexus.agents.sql_agent import SQLAgent, SQLGuardrailError, sql_agent


def test_valid_query_returns_rows() -> None:
    sql, rows, dur = sql_agent.execute_query("Show tickets for Apollo Global Healthcare")
    assert "ACC-101" in sql
    assert len(rows) > 0
    assert dur >= 0.0


def test_drop_in_user_query_blocked() -> None:
    with pytest.raises(SQLGuardrailError):
        sql_agent.execute_query("DROP TABLE accounts")


def test_delete_in_user_query_blocked() -> None:
    with pytest.raises(SQLGuardrailError):
        sql_agent.execute_query("please delete all incident tickets")


def test_single_select_guard_rejects_multi_statement() -> None:
    with pytest.raises(SQLGuardrailError):
        SQLAgent._assert_single_select("SELECT 1; SELECT 2")


def test_single_select_guard_rejects_non_select() -> None:
    with pytest.raises(SQLGuardrailError):
        SQLAgent._assert_single_select("EXPLAIN SELECT 1")


def test_readonly_connection_rejects_write_at_engine_level() -> None:
    conn = sql_agent._connect_readonly()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO accounts VALUES ('ACC-999','X','Gold',1.0,'Y','ACTIVE')")
    finally:
        conn.close()


def test_schema_introspection_reads_catalog() -> None:
    schema = sql_agent.introspect_schema()
    assert "accounts" in schema
    assert "incident_tickets" in schema
    assert "mrr_usd" in schema["accounts"]
