"""Hybrid retrieval: Okapi BM25 + a pluggable dense channel, fused with RRF.

Dense defaults to TF-IDF cosine (see embeddings.py). The BM25 and dense rank
lists are combined with Reciprocal Rank Fusion (k=60).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np

from nexus.logging import get_logger
from nexus.rag.document_store import document_store
from nexus.rag.embeddings import EmbeddingProvider, TfidfEmbedder, get_embedder, tokenize
from nexus.state import Citation

logger = get_logger(__name__)

__all__ = ["OkapiBM25", "HybridRetriever", "hybrid_retriever", "tokenize"]


class OkapiBM25:
    """Okapi BM25 ranking over a fixed corpus."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.n_docs = len(corpus_tokens)
        self.doc_freqs = [Counter(doc) for doc in corpus_tokens]
        self.doc_len = np.array([len(doc) for doc in corpus_tokens], dtype=float)
        self.avgdl = float(self.doc_len.mean()) if self.n_docs else 0.0

        document_frequency: Counter[str] = Counter()
        for doc in corpus_tokens:
            document_frequency.update(set(doc))
        # +1 smoothing keeps every idf non-negative.
        self.idf = {
            term: math.log(1.0 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in document_frequency.items()
        }

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        out = np.zeros(self.n_docs, dtype=float)
        if not self.n_docs or self.avgdl == 0.0:
            return out
        for term in query_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i in range(self.n_docs):
                tf = self.doc_freqs[i].get(term, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (1.0 - self.b + self.b * self.doc_len[i] / self.avgdl)
                out[i] += idf * (tf * (self.k1 + 1.0)) / denom
        return out


class HybridRetriever:
    def __init__(self, rrf_k: int = 60) -> None:
        self.rrf_k = rrf_k
        self._build()

    def _build(self) -> None:
        self.docs: list[dict[str, Any]] = document_store.get_all()
        corpus_tokens = [tokenize(d["title"] + " " + d["content"]) for d in self.docs]
        self.bm25 = OkapiBM25(corpus_tokens)
        self.embedder: EmbeddingProvider = get_embedder()
        self.doc_matrix = self._embed_corpus([d["title"] + " " + d["content"] for d in self.docs])

    def _embed_corpus(self, doc_texts: list[str]) -> np.ndarray:
        if not self.docs:
            return np.zeros((0, 0), dtype=float)
        try:
            return self.embedder.embed_documents(doc_texts)
        except Exception as exc:
            # A failing embedder (e.g. Gemini network error) must not take the
            # gateway down at startup: fall back to the offline TF-IDF channel.
            logger.warning(
                "Dense embedder '%s' failed (%s); falling back to TF-IDF",
                self.embedder.name,
                exc,
            )
            self.embedder = TfidfEmbedder()
            return self.embedder.embed_documents(doc_texts)

    def _dense_scores(self, query: str) -> np.ndarray:
        if self.doc_matrix.size == 0:
            return np.zeros(len(self.docs), dtype=float)
        return self.doc_matrix @ self.embedder.embed_query(query)

    @staticmethod
    def _rank_map(scores: np.ndarray) -> dict[int, int]:
        order = np.argsort(-scores, kind="stable")
        return {int(idx): rank for rank, idx in enumerate(order)}

    def retrieve(self, query: str, top_k: int = 3) -> list[Citation]:
        if not self.docs:
            self._build()
        if not self.docs:
            return []

        sparse = self.bm25.scores(tokenize(query))
        dense = self._dense_scores(query)
        sparse_rank = self._rank_map(sparse)
        dense_rank = self._rank_map(dense)

        fused: list[tuple[int, float]] = []
        for i in range(len(self.docs)):
            rrf = 1.0 / (self.rrf_k + sparse_rank[i]) + 1.0 / (self.rrf_k + dense_rank[i])
            fused.append((i, rrf))
        fused.sort(key=lambda pair: pair[1], reverse=True)

        citations: list[Citation] = []
        for doc_idx, rrf_score in fused[:top_k]:
            doc = self.docs[doc_idx]
            content = doc["content"]
            snippet = content[:240] + ("..." if len(content) > 240 else "")
            citations.append(
                Citation(
                    document_id=doc["id"],
                    section_title=doc["title"],
                    snippet=snippet,
                    relevance_score=round(rrf_score * 1000.0, 4),
                    bm25_score=round(float(sparse[doc_idx]), 4),
                    dense_score=round(float(dense[doc_idx]), 4),
                )
            )
        return citations


hybrid_retriever = HybridRetriever()
