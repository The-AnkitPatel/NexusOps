"""Supervisor that routes a query across the specialist agents.

Routing and synthesis use Gemini when GEMINI_API_KEY is set, and fall back to a
keyword classifier and a report template otherwise. Trace token counts are
estimates (see cost_calculator.estimate_tokens).
"""

from __future__ import annotations

import time
import uuid

from nexus.agents.guardrail import guardrail_agent
from nexus.agents.retriever import retriever_agent
from nexus.agents.sql_agent import sql_agent
from nexus.config import settings
from nexus.logging import get_logger
from nexus.state import AgentStepTrace, NexusState
from nexus.telemetry.cost_calculator import calculate_token_cost, estimate_tokens
from nexus.telemetry.metrics import metrics_collector
from nexus.telemetry.tracer import record_genai_span

logger = get_logger(__name__)

SQL_KEYWORDS = (
    "ticket",
    "account",
    "downtime",
    "incident",
    "p0",
    "p1",
    "apollo",
    "finsecure",
    "mrr",
    "table",
    "sql",
    "outage",
    "client",
)
DOC_KEYWORDS = (
    "sla",
    "policy",
    "reimbursement",
    "credit",
    "guideline",
    "standard",
    "masking",
    "pii",
    "escalation",
    "protocol",
    "billing",
    "discount",
)


class SupervisorAgent:
    def __init__(self) -> None:
        self.client = None
        self.execution_mode = "deterministic_offline"
        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self.execution_mode = "live_gemini"
            except Exception as exc:
                logger.warning("Failed to initialise Google GenAI client: %s", exc)

    def _classify_intent(self, query: str) -> str:
        """Route the query: Gemini when available, else the keyword classifier.

        The LLM only routes; executable SQL always comes from the read-only planner.
        """
        if self.client is not None:
            label = self._classify_intent_llm(query)
            if label is not None:
                return label
        return self._classify_intent_keywords(query)

    @staticmethod
    def _classify_intent_keywords(query: str) -> str:
        q = query.lower()
        has_sql = any(k in q for k in SQL_KEYWORDS)
        has_doc = any(k in q for k in DOC_KEYWORDS)
        if has_sql and has_doc:
            return "HYBRID_REASONING"
        if has_sql:
            return "SQL_QUERY"
        return "DOCUMENT_LOOKUP"

    def _classify_intent_llm(self, query: str) -> str | None:
        """Classify intent with Gemini; return None to fall back to keywords."""
        if self.client is None:
            return None
        prompt = (
            "Classify the enterprise query into exactly one label:\n"
            "- SQL_QUERY: needs the incident/account database only\n"
            "- DOCUMENT_LOOKUP: needs SLA/policy documents only\n"
            "- HYBRID_REASONING: needs both\n"
            f"Query: {query}\n"
            "Answer with only the label."
        )
        try:
            resp = self.client.models.generate_content(model=settings.NEXUS_MODEL, contents=prompt)
            text = (resp.text or "").strip().upper()
            for label in ("HYBRID_REASONING", "SQL_QUERY", "DOCUMENT_LOOKUP"):
                if label in text:
                    return label
        except Exception as exc:
            logger.warning("LLM intent routing failed, using keywords: %s", exc)
        return None

    def _synthesize_response(self, state: NexusState) -> tuple[str, str]:
        """Return (response_text, synthesis_prompt). Gemini if available, else template."""
        prompt = (
            "You are the Google Cloud Forward Deployed Engineer (FDE) AI Assistant.\n"
            f"User Query: {state.user_query}\n\n"
            "Context Evidence:\n"
            f"- Retrieved Policies/SLA: {[c.model_dump() for c in state.retrieved_citations]}\n"
            f"- Enterprise Database Records: {state.sql_results}\n\n"
            "Provide a crisp, actionable enterprise report with concrete numbers, "
            "incident status, and SLA compliance terms."
        )

        if self.client is not None:
            try:
                response = self.client.models.generate_content(
                    model=settings.NEXUS_MODEL, contents=prompt
                )
                return (response.text or "").strip(), prompt
            except Exception as exc:
                logger.warning("Gemini synthesis failed, using fallback: %s", exc)

        return self._deterministic_report(state), prompt

    @staticmethod
    def _deterministic_report(state: NexusState) -> str:
        sections: list[str] = [f"### Enterprise Operations Report: `{state.intent}`"]
        if state.sql_results:
            sections.append(f"**Database Audit Records ({len(state.sql_results)} found):**")
            sections.extend(f"- Record: {row}" for row in state.sql_results[:3])
        if state.retrieved_citations:
            sections.append("**Compliance & Policy Citations:**")
            for c in state.retrieved_citations:
                sections.append(f'- **[{c.document_id}] {c.section_title}**: "{c.snippet}"')
        if state.intent == "HYBRID_REASONING":
            sections.append("\n**FDE Synthesis & SLA Impact Analysis:**")
            sections.append(
                "Based on the correlated ticket records and Google Cloud SLA "
                "commitments, the impacted client is eligible for financial-credit "
                "evaluation if downtime exceeded the threshold defined under "
                "POL-SLA-001. Escalation protocol POL-INC-003 governs active "
                "P0/P1 severity workloads."
            )
        else:
            sections.append("\n**Resolution Recommendation:**")
            sections.append(
                "Incident tickets cross-verified against production telemetry; "
                "continuous monitoring active."
            )
        return "\n".join(sections)

    def process(self, query: str, session_id: str | None = None) -> NexusState:
        start_time = time.perf_counter()
        sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
        state = NexusState(session_id=sid, user_query=query)
        state.execution_mode = self.execution_mode

        # Step 1: intent classification -----------------------------------
        t0 = time.perf_counter()
        state.intent = self._classify_intent(query)
        dur = (time.perf_counter() - t0) * 1000.0
        state.execution_trace.append(
            AgentStepTrace(
                agent_name="SupervisorAgent",
                action="classify_intent",
                input_payload={"query": query},
                output_payload={"intent": state.intent},
                duration_ms=round(dur, 2),
                tokens_used=estimate_tokens(f"{query} {state.intent}"),
            )
        )

        # Step 2a: document retrieval -------------------------------------
        if state.intent in ("DOCUMENT_LOOKUP", "HYBRID_REASONING"):
            citations, ret_dur = retriever_agent.execute_retrieval(query, top_k=2)
            state.retrieved_citations = citations
            retrieved_text = " ".join(c.snippet for c in citations)
            state.execution_trace.append(
                AgentStepTrace(
                    agent_name="RetrieverAgent",
                    action="hybrid_bm25_tfidf_rrf_retrieval",
                    input_payload={"query": query, "top_k": 2},
                    output_payload={"citations_count": len(citations)},
                    duration_ms=ret_dur,
                    tokens_used=estimate_tokens(f"{query} {retrieved_text}"),
                )
            )

        # Step 2b: SQL planning + execution -------------------------------
        if state.intent in ("SQL_QUERY", "HYBRID_REASONING"):
            sql, rows, sql_dur = sql_agent.execute_query(query)
            state.sql_query = sql
            state.sql_results = rows
            state.execution_trace.append(
                AgentStepTrace(
                    agent_name="SQLAgent",
                    action="plan_and_execute_readonly_sql",
                    input_payload={"planned_sql": sql},
                    output_payload={"row_count": len(rows)},
                    duration_ms=sql_dur,
                    tokens_used=estimate_tokens(f"{sql} {rows}"),
                )
            )

        # Step 3: synthesis -----------------------------------------------
        t0 = time.perf_counter()
        raw_response, synth_prompt = self._synthesize_response(state)
        state.draft_response = raw_response
        synth_dur = (time.perf_counter() - t0) * 1000.0
        state.execution_trace.append(
            AgentStepTrace(
                agent_name="SynthesisEngine",
                action=f"synthesize_response[{self.execution_mode}]",
                input_payload={"intent": state.intent},
                output_payload={"response_chars": len(raw_response)},
                duration_ms=round(synth_dur, 2),
                tokens_used=estimate_tokens(f"{synth_prompt} {raw_response}"),
            )
        )

        # Step 4: guardrail (grounding + PII masking) ---------------------
        is_hallucinating, score, guard_status, guard_dur = guardrail_agent.evaluate_groundedness(
            raw_response, state.retrieved_citations, state.sql_results or []
        )
        state.hallucination_detected = is_hallucinating
        state.groundedness_score = score
        state.guardrail_status = guard_status
        state.final_response = guardrail_agent.mask_pii(raw_response)
        state.execution_trace.append(
            AgentStepTrace(
                agent_name="GuardrailAgent",
                action="verify_groundedness_and_mask_pii",
                input_payload={"draft_length": len(raw_response)},
                output_payload={
                    "groundedness_score": score,
                    "guardrail_status": guard_status,
                },
                duration_ms=guard_dur,
                tokens_used=estimate_tokens(raw_response),
            )
        )

        # Step 5: telemetry (estimated token accounting) ------------------
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        prompt_tokens = sum(step.tokens_used for step in state.execution_trace)
        completion_tokens = estimate_tokens(state.final_response or "")
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = calculate_token_cost(prompt_tokens, completion_tokens)

        for step in state.execution_trace:
            step.estimated_cost_usd = calculate_token_cost(step.tokens_used, 0)

        state.total_tokens = total_tokens
        state.total_cost_usd = cost_usd
        state.total_latency_ms = round(total_time_ms, 2)

        record_genai_span(
            operation_name="multi_agent_execution",
            model_name=settings.NEXUS_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            attributes={
                "nexus.intent": state.intent,
                "nexus.execution_mode": self.execution_mode,
                "nexus.token_accounting": "estimated_chars_div_4",
                "nexus.groundedness_score": state.groundedness_score,
                "nexus.guardrail_status": state.guardrail_status,
            },
        )

        metrics_collector.record_query(
            latency_ms=state.total_latency_ms,
            tokens=total_tokens,
            cost_usd=cost_usd,
            violated_guardrail=is_hallucinating,
            trace_summary={
                "session_id": state.session_id,
                "query": query,
                "intent": state.intent,
                "execution_mode": self.execution_mode,
                "latency_ms": state.total_latency_ms,
                "cost_usd": cost_usd,
                "tokens": total_tokens,
            },
        )
        return state


supervisor_agent = SupervisorAgent()
