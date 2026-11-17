"""Schema-aware SQL planner with read-only execution.

Maps a query to one of a fixed set of parameter-free SELECT templates and runs it
on a read-only connection. Guardrails:

1. mode=ro URI connection (the engine rejects writes).
2. PRAGMA query_only = ON.
3. single-statement SELECT/WITH check + forbidden-keyword scan, applied to both
   the user query and the planned SQL.
"""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any

from nexus.config import settings
from nexus.logging import get_logger

logger = get_logger(__name__)

_FORBIDDEN = (
    "drop",
    "delete",
    "truncate",
    "update",
    "insert",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "pragma",
    "grant",
    "vacuum",
)


class SQLGuardrailError(ValueError):
    """Raised when a query is rejected by the read-only guardrail."""


class SQLAgent:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.DATABASE_PATH

    # -- connection ---------------------------------------------------------
    def _connect_readonly(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON;")
        return conn

    def introspect_schema(self) -> dict[str, list[str]]:
        """Return {table: [columns]} read live from the database catalog."""
        schema: dict[str, list[str]] = {}
        conn = self._connect_readonly()
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            for row in tables:
                table = row["name"]
                cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                schema[table] = [c["name"] for c in cols]
        finally:
            conn.close()
        return schema

    # -- planning -----------------------------------------------------------
    def plan_sql(self, query: str) -> str:
        """Map a natural-language query to a vetted read-only SELECT template."""
        q = query.lower()
        if "apollo" in q:
            return (
                "SELECT ticket_id, severity, service_impacted, downtime_minutes, status "
                "FROM incident_tickets WHERE account_id = 'ACC-101'"
            )
        if "finsecure" in q or "bank" in q:
            return (
                "SELECT ticket_id, severity, service_impacted, downtime_minutes, status "
                "FROM incident_tickets WHERE account_id = 'ACC-102'"
            )
        if "p0" in q or "p1" in q or "critical" in q:
            return (
                "SELECT a.company_name, t.ticket_id, t.severity, t.service_impacted, "
                "t.downtime_minutes FROM incident_tickets t "
                "JOIN accounts a ON t.account_id = a.account_id "
                "WHERE t.severity IN ('P0', 'P1')"
            )
        if "downtime" in q or "outage" in q:
            return (
                "SELECT a.company_name, SUM(t.downtime_minutes) AS total_downtime, "
                "COUNT(t.ticket_id) AS total_tickets FROM incident_tickets t "
                "JOIN accounts a ON t.account_id = a.account_id GROUP BY a.company_name"
            )
        if "account" in q or "client" in q or "mrr" in q:
            return (
                "SELECT account_id, company_name, tier, mrr_usd, assigned_fde "
                "FROM accounts ORDER BY mrr_usd DESC"
            )
        return (
            "SELECT ticket_id, account_id, severity, service_impacted, status "
            "FROM incident_tickets LIMIT 5"
        )

    # -- guardrails ---------------------------------------------------------
    def _assert_safe(self, text: str, label: str) -> None:
        for word in _FORBIDDEN:
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                logger.warning("Read-only guardrail blocked %s (forbidden token: %s)", label, word)
                raise SQLGuardrailError(
                    f"Read-only guardrail blocked {label}: '{word}' is not permitted"
                )

    @staticmethod
    def _assert_single_select(sql: str) -> None:
        stripped = sql.strip().rstrip(";")
        if ";" in stripped:
            raise SQLGuardrailError("Multiple SQL statements are not permitted")
        if not re.match(r"(?is)^\s*(select|with)\b", stripped):
            raise SQLGuardrailError("Only SELECT / WITH read queries are permitted")

    # -- execution ----------------------------------------------------------
    def execute_query(self, query: str) -> tuple[str, list[dict[str, Any]], float]:
        start = time.perf_counter()
        self._assert_safe(query, "user query")

        sql = self.plan_sql(query)
        self._assert_safe(sql, "planned SQL")
        self._assert_single_select(sql)

        conn = self._connect_readonly()
        try:
            results = [dict(row) for row in conn.execute(sql).fetchall()]
        finally:
            conn.close()

        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
        return sql, results, duration_ms


sql_agent = SQLAgent()
