import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "enterprise_tickets.db")

def initialize_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create Accounts Table
    cursor.execute("""
    CREATE TABLE accounts (
        account_id TEXT PRIMARY KEY,
        company_name TEXT NOT NULL,
        tier TEXT NOT NULL, -- Enterprise Platinum, Gold, Silver
        mrr_usd REAL NOT NULL,
        assigned_fde TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """)

    # Create Incident Tickets Table
    cursor.execute("""
    CREATE TABLE incident_tickets (
        ticket_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        severity TEXT NOT NULL, -- P0, P1, P2, P3
        service_impacted TEXT NOT NULL,
        description TEXT NOT NULL,
        downtime_minutes INTEGER DEFAULT 0,
        status TEXT NOT NULL, -- OPEN, IN_PROGRESS, RESOLVED
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
    )
    """)

    # Seed Accounts
    accounts = [
        ("ACC-101", "Apollo Global Healthcare", "Enterprise Platinum", 185000.0, "Ankit Patel", "ACTIVE"),
        ("ACC-102", "FinSecure Bharat Bank", "Enterprise Platinum", 320000.0, "Ankit Patel", "ACTIVE"),
        ("ACC-103", "Himalayan Logistics Corp", "Enterprise Gold", 65000.0, "Sarah Jenkins", "ACTIVE"),
        ("ACC-104", "RetailPulse Commerce", "Enterprise Silver", 28000.0, "David Chen", "ACTIVE"),
        ("ACC-105", "Apex Telecom Telemetry", "Enterprise Platinum", 240000.0, "Ankit Patel", "ACTIVE")
    ]
    cursor.executemany("INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?)", accounts)

    # Seed Tickets
    tickets = [
        ("TCK-901", "ACC-101", "P1", "Cloud SQL Postgres", "Primary replica failover timeout during high load, connection pool exhaustion", 42, "RESOLVED", "2026-11-10 14:15:00", "2026-11-10 14:57:00"),
        ("TCK-902", "ACC-102", "P0", "Vertex AI Prediction Endpoint", "Spike in 503 Service Unavailable during credit risk scoring pipeline", 18, "RESOLVED", "2026-11-12 09:30:00", "2026-11-12 09:48:00"),
        ("TCK-903", "ACC-105", "P2", "BigQuery Telemetry Pipeline", "Streaming buffer ingestion delay exceeding 120s on network telemetry sink", 0, "IN_PROGRESS", "2026-11-15 18:20:00", None),
        ("TCK-904", "ACC-103", "P3", "Cloud Storage Multi-Region", "Coldline archive bucket IAM permission propagation delay", 0, "RESOLVED", "2026-11-08 11:00:00", "2026-11-08 11:45:00"),
        ("TCK-905", "ACC-101", "P1", "GKE Autopilot Workload", "Node pool autoscaling quota reached during hospital night admissions batch", 35, "OPEN", "2026-11-16 22:10:00", None)
    ]
    cursor.executemany("INSERT INTO incident_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tickets)

    conn.commit()
    conn.close()
    print(f"Enterprise database initialized at {DB_PATH}")

if __name__ == "__main__":
    initialize_database()
