from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

class Citation(BaseModel):
    document_id: str
    section_title: str
    snippet: str
    relevance_score: float

class AgentStepTrace(BaseModel):
    agent_name: str
    action: str
    input_payload: Dict[str, Any]
    output_payload: Dict[str, Any]
    duration_ms: float
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0

class NexusState(BaseModel):
    session_id: str
    user_query: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Routing & Intent
    intent: Optional[str] = None  # "DOCUMENT_LOOKUP", "SQL_QUERY", "HYBRID_REASONING"
    
    # Retrieved & Structured Context
    retrieved_citations: List[Citation] = Field(default_factory=list)
    sql_query: Optional[str] = None
    sql_results: Optional[List[Dict[str, Any]]] = None
    
    # Generation & Evaluation
    draft_response: Optional[str] = None
    final_response: Optional[str] = None
    hallucination_detected: bool = False
    groundedness_score: float = 1.0  # 0.0 to 1.0
    guardrail_status: str = "PENDING"  # "PASSED", "FLAGGED", "INTERCEPTED"
    
    # OpenTelemetry Tracing
    execution_trace: List[AgentStepTrace] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
