import sqlite3
import re
import time
from typing import Dict, Any, List, Tuple
from nexus.config import settings

class SQLAgent:
    def __init__(self, db_path: str = settings.DATABASE_PATH):
        self.db_path = db_path

    def _generate_sql(self, query: str) -> str:
        """
        Translates natural language questions into safe SELECT queries.
        In production FDE setting, this is guided by prompt constraints & schema introspection.
        """
        q = query.lower()
        
        if "apollo" in q:
            return "SELECT ticket_id, severity, service_impacted, downtime_minutes, status FROM incident_tickets WHERE account_id = 'ACC-101'"
        elif "finsecure" in q or "bank" in q:
            return "SELECT ticket_id, severity, service_impacted, downtime_minutes, status FROM incident_tickets WHERE account_id = 'ACC-102'"
        elif "p0" in q or "p1" in q or "critical" in q:
            return "SELECT a.company_name, t.ticket_id, t.severity, t.service_impacted, t.downtime_minutes FROM incident_tickets t JOIN accounts a ON t.account_id = a.account_id WHERE t.severity IN ('P0', 'P1')"
        elif "downtime" in q or "outage" in q:
            return "SELECT a.company_name, SUM(t.downtime_minutes) as total_downtime, COUNT(t.ticket_id) as total_tickets FROM incident_tickets t JOIN accounts a ON t.account_id = a.account_id GROUP BY a.company_name"
        elif "account" in q or "client" in q or "mrr" in q:
            return "SELECT account_id, company_name, tier, mrr_usd, assigned_fde FROM accounts ORDER BY mrr_usd DESC"
        else:
            return "SELECT ticket_id, account_id, severity, service_impacted, status FROM incident_tickets LIMIT 5"

    def execute_query(self, query: str) -> Tuple[str, List[Dict[str, Any]], float]:
        start = time.time()
        
        # Security Guardrail: Reject destructive statements in raw query or generated SQL
        forbidden = ["drop", "delete", "truncate", "update", "insert", "alter"]
        for word in forbidden:
            if re.search(rf"\b{word}\b", query, re.IGNORECASE):
                raise ValueError(f"Dangerous SQL query blocked by FDE Guardrail: {word}")

        sql = self._generate_sql(query)
        for word in forbidden:
            if re.search(rf"\b{word}\b", sql, re.IGNORECASE):
                raise ValueError(f"Dangerous SQL query blocked by FDE Guardrail: {word}")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        duration_ms = (time.time() - start) * 1000.0
        
        return sql, results, round(duration_ms, 2)

sql_agent = SQLAgent()
