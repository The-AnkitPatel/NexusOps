"""Correctness of BM25, TF-IDF cosine, and RRF-fused hybrid retrieval."""

from __future__ import annotations

from nexus.rag.hybrid_search import (
    OkapiBM25,
    TfidfIndex,
    hybrid_retriever,
    tokenize,
)


def test_bm25_ranks_matching_doc_higher() -> None:
    corpus = [
        tokenize("cloud sql high availability uptime commitment"),
        tokenize("committed use discount billing reallocation"),
    ]
    scores = OkapiBM25(corpus).scores(tokenize("uptime sql"))
    assert scores[0] > scores[1]


def test_tfidf_cosine_in_unit_range_and_discriminates() -> None:
    corpus = [
        tokenize("pii masking tokenization data sovereignty"),
        tokenize("sla uptime financial credit"),
    ]
    scores = TfidfIndex(corpus).scores(tokenize("pii masking"))
    assert 0.0 <= scores[0] <= 1.0 + 1e-9
    assert scores[0] > scores[1]


def test_hybrid_retrieves_sla_policy() -> None:
    citations = hybrid_retriever.retrieve(
        "What is the uptime SLA for Cloud SQL High Availability?", top_k=2
    )
    assert citations
    assert citations[0].document_id == "POL-SLA-001"
    assert citations[0].bm25_score > 0.0
    assert citations[0].relevance_score > 0.0


def test_hybrid_retrieves_pii_policy_top1() -> None:
    citations = hybrid_retriever.retrieve("data protection and PII masking standards", top_k=1)
    assert len(citations) == 1
    assert citations[0].document_id == "POL-SEC-002"


def test_retrieve_empty_query_is_safe() -> None:
    citations = hybrid_retriever.retrieve("", top_k=2)
    assert isinstance(citations, list)
    assert len(citations) <= 2
