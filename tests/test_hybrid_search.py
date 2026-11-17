import pytest
from nexus.rag.hybrid_search import hybrid_retriever

def test_hybrid_search_retrieves_sla():
    citations = hybrid_retriever.retrieve("What is the uptime SLA for Cloud SQL High Availability?", top_k=2)
    assert len(citations) > 0
    assert any("SLA" in c.document_id or "SLA" in c.section_title for c in citations)
    assert citations[0].relevance_score > 0.0

def test_hybrid_search_retrieves_pii_policy():
    citations = hybrid_retriever.retrieve("data protection and PII masking standards", top_k=1)
    assert len(citations) == 1
    assert "POL-SEC-002" in citations[0].document_id
