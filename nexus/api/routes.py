from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from nexus.agents.supervisor import supervisor_agent
from nexus.telemetry.metrics import metrics_collector
from nexus.state import NexusState

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class EvalRequest(BaseModel):
    response_text: str
    context_snippets: List[str]

@router.post("/v1/agent/query", response_model=NexusState)
def execute_agent_query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return supervisor_agent.process(req.query, session_id=req.session_id)

@router.get("/v1/telemetry/metrics")
def get_telemetry_metrics() -> Dict[str, Any]:
    return metrics_collector.get_metrics_summary()

@router.get("/v1/telemetry/traces")
def get_recent_traces() -> List[Dict[str, Any]]:
    return metrics_collector.traces[-50:]

@router.get("/v1/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "HEALTHY", "system": "NexusOps Enterprise Gateway", "version": "0.1.0"}
