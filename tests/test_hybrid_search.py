"""Correctness of BM25, the TF-IDF embedder, and RRF-fused hybrid retrieval."""

from __future__ import annotations

from nexus.rag.embeddings import TfidfEmbedder, get_embedder
from nexus.rag.hybrid_search import OkapiBM25, hybrid_retriever, tokenize


def test_bm25_ranks_matching_doc_higher() -> None:
    corpus = [
        tokenize("cloud sql high availability uptime commitment"),
        tokenize("committed use discount billing reallocation"),
    ]
    scores = OkapiBM25(corpus).scores(tokenize("uptime sql"))
    assert scores[0] > scores[1]


def test_tfidf_embedder_cosine_in_unit_range_and_discriminates() -> None:
    emb = TfidfEmbedder()
    matrix = emb.embed_documents(
        [
            "pii masking tokenization data sovereignty",
            "sla uptime financial credit",
        ]
    )
    scores = matrix @ emb.embed_query("pii masking")
    assert 0.0 <= scores[0] <= 1.0 + 1e-9
    assert scores[0] > scores[1]


def test_default_embedder_is_tfidf_offline() -> None:
    assert get_embedder().name == "tfidf"


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
