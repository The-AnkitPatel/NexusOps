import json
import os
import sqlite3
import sys

import altair as alt
import pandas as pd
import streamlit as st

# Ensure nexus package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nexus.agents.supervisor import supervisor_agent
from nexus.config import settings
from nexus.telemetry.metrics import metrics_collector
from nexus.telemetry.tracer import otlp_enabled

st.set_page_config(page_title="NexusOps | Google Cloud FDE Gateway", page_icon="🛡️", layout="wide")

# Header
st.title("🛡️ NexusOps — Forward Deployed Enterprise Agentic Gateway")
st.caption(
    "Multi-agent orchestration · Hybrid retrieval (BM25 + TF-IDF via RRF) · Read-only SQL planning · OpenTelemetry GenAI telemetry"
)

_mode = supervisor_agent.execution_mode
_mode_label = "🟢 Live Gemini" if _mode == "live_gemini" else "⚙️ Deterministic offline (no API key)"
_otlp_label = "OTLP export: on" if otlp_enabled else "OTLP export: in-memory only"
st.caption(
    f"**Mode:** {_mode_label}  ·  {_otlp_label}  ·  token counts are *estimated* (~4 chars/token) in offline mode"
)

# Tabs
tab_agent, tab_telemetry, tab_data = st.tabs(
    ["🤖 Agent Command Center", "📊 OpenTelemetry & Cost Analytics", "🗄️ Enterprise Data Readiness"]
)

# ----------------- TAB 1: AGENT COMMAND CENTER -----------------
with tab_agent:
    st.subheader("Enterprise Incident & SLA Reasoning")

    col_preset, col_custom = st.columns([1, 2])
    with col_preset:
        preset = st.selectbox(
            "Select Scenario Template:",
            [
                "Custom Prompt",
                "Check Apollo Healthcare P1 outage and verify SLA reimbursement credit",
                "List all P0/P1 incidents across Platinum accounts and total downtime",
                "What is the enterprise PII masking standard under POL-SEC-002?",
                "Identify top 5 enterprise accounts by MRR and their assigned FDE",
            ],
        )

    with col_custom:
        if preset == "Custom Prompt":
            query = st.text_input(
                "Enter Enterprise Query:",
                value="Does Apollo Healthcare qualify for an SLA credit on their Cloud SQL P1 ticket?",
            )
        else:
            query = st.text_input("Enter Enterprise Query:", value=preset)

    if st.button("🚀 Execute Multi-Agent Workflow", type="primary"):
        with st.spinner("Orchestrating agents & recording OpenTelemetry spans..."):
            state = supervisor_agent.process(query)

        st.success(
            f"Execution completed in {state.total_latency_ms} ms | Tokens: {state.total_tokens} | Cost: ${state.total_cost_usd:.6f}"
        )

        # Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Routing Intent", state.intent)
        col2.metric("Groundedness (proxy)", f"{int(state.groundedness_score * 100)}%")
        col3.metric("Guardrail Status", state.guardrail_status)
        col4.metric("Est. Cost", f"${state.total_cost_usd:.6f}")

        # Execution Trace — Gantt timeline + per-step table
        st.markdown("#### ⚡ Agent Execution Trace")
        trace_data = []
        gantt_rows = []
        elapsed = 0.0
        for step in state.execution_trace:
            gantt_rows.append(
                {
                    "Agent": step.agent_name,
                    "Action": step.action,
                    "start": elapsed,
                    "end": elapsed + step.duration_ms,
                    "ms": step.duration_ms,
                }
            )
            elapsed += step.duration_ms
            trace_data.append(
                {
                    "Agent": step.agent_name,
                    "Action": step.action,
                    "Duration (ms)": step.duration_ms,
                    "Tokens (est.)": step.tokens_used,
                    "Est. Cost ($)": round(step.estimated_cost_usd, 6),
                }
            )

        gantt = (
            alt.Chart(pd.DataFrame(gantt_rows))
            .mark_bar(cornerRadius=3, height=18)
            .encode(
                x=alt.X("start:Q", title="Elapsed (ms)"),
                x2="end:Q",
                y=alt.Y("Agent:N", sort=None, title=None),
                color=alt.Color("Agent:N", legend=None),
                tooltip=["Agent", "Action", "ms"],
            )
            .properties(height=160)
        )
        st.altair_chart(gantt, use_container_width=True)
        st.dataframe(pd.DataFrame(trace_data), use_container_width=True)

        # Context details
        col_sql, col_rag = st.columns(2)
        with col_sql:
            st.markdown("##### 🗄️ Structured Database Evidence")
            if state.sql_query:
                st.code(state.sql_query, language="sql")
            if state.sql_results:
                st.dataframe(pd.DataFrame(state.sql_results), use_container_width=True)
            else:
                st.info("No SQL database query required for this intent.")

        with col_rag:
            st.markdown("##### 📄 Verified Grounded Citations")
            if state.retrieved_citations:
                for c in state.retrieved_citations:
                    with st.expander(
                        f"📌 [{c.document_id}] {c.section_title} (RRF: {c.relevance_score})"
                    ):
                        st.caption(
                            f"BM25 (sparse): {c.bm25_score}  ·  TF-IDF cosine (dense): {c.dense_score}"
                        )
                        st.write(c.snippet)
            else:
                st.info("No policy documents retrieved for this intent.")

        # Final Synthesized Report
        st.markdown("#### 📝 Final Synthesized FDE Output")
        st.markdown(state.final_response)

# ----------------- TAB 2: OPENTELEMETRY & COST ANALYTICS -----------------
with tab_telemetry:
    st.subheader("OpenTelemetry GenAI Semantic Metrics")
    summary = metrics_collector.get_metrics_summary()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Invocations", summary["total_queries"])
    kpi2.metric("p95 Latency", f"{summary['p95_latency_ms']} ms")
    kpi3.metric("Total Token Spend", f"${summary['total_cost_usd']}")
    kpi4.metric("Guardrail Interceptions", summary["guardrail_intercept_rate"])

    st.caption(
        "Token/cost figures are estimated (~4 chars/token) in offline mode; a live "
        "provider's usage metadata would replace them. Spans follow GenAI semantic "
        "conventions and also ship over OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is set."
    )

    st.markdown("#### 📡 Real-Time Trace Log (OpenTelemetry InMemory Exporter)")
    if metrics_collector.traces:
        st.dataframe(pd.DataFrame(metrics_collector.traces), use_container_width=True)
    else:
        st.info("Run an agent query from the Command Center to populate live traces.")

# ----------------- TAB 3: ENTERPRISE DATA READINESS -----------------
with tab_data:
    st.subheader("Enterprise Datastore Inspector")

    ro_uri = f"file:{settings.DATABASE_PATH}?mode=ro"
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("##### 🏢 Accounts & MRR")
        conn = sqlite3.connect(ro_uri, uri=True)
        df_acc = pd.read_sql_query("SELECT * FROM accounts", conn)
        st.dataframe(df_acc, use_container_width=True)
        conn.close()

    with col_d2:
        st.markdown("##### 🎫 Incident Tickets")
        conn = sqlite3.connect(ro_uri, uri=True)
        df_tck = pd.read_sql_query("SELECT * FROM incident_tickets", conn)
        st.dataframe(df_tck, use_container_width=True)
        conn.close()

    st.markdown("##### 📜 Ingested Cloud Policies & SLAs")
    with open(settings.POLICIES_PATH) as f:
        policies = json.load(f)
    for p in policies:
        with st.expander(f"📘 {p['id']} — {p['title']}"):
            st.write(f"**Category:** `{p['category']}` | **Effective Date:** {p['effective_date']}")
            st.write(p["content"])
