"""Hybrid retrieval: Okapi BM25 (sparse) + TF-IDF cosine (dense), fused with RRF.

Design note (honesty first): the "dense" channel is a genuine TF-IDF vector space
with L2-normalised cosine similarity -- a real vector retrieval method, computed
exactly on numpy. It is deliberately NOT a neural embedding, so the gateway runs
fully offline with no model download, no embedding service, and no API key. Both
channels are standard, textbook-correct implementations; they are fused with
Reciprocal Rank Fusion (RRF, k=60), the same rank-combination used by production
hybrid search stacks (e.g. Elasticsearch, Vespa).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import numpy as np

from nexus.rag.document_store import document_store
from nexus.state import Citation

_TOKEN_RE = re.compile(r"\b\w+\b")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class OkapiBM25:
    """Textbook Okapi BM25 ranking over a fixed corpus."""

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
        # BM25 idf with +1 smoothing so every score stays non-negative.
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


class TfidfIndex:
    """TF-IDF vector space with L2-normalised cosine similarity."""

    def __init__(self, corpus_tokens: list[list[str]]) -> None:
        self.vocab: dict[str, int] = {}
        for doc in corpus_tokens:
            for term in doc:
                if term not in self.vocab:
                    self.vocab[term] = len(self.vocab)

        n_docs = len(corpus_tokens)
        vocab_size = len(self.vocab)
        df = np.zeros(vocab_size, dtype=float)
        for doc in corpus_tokens:
            for term in set(doc):
                df[self.vocab[term]] += 1.0
        # Smoothed idf (scikit-learn convention): log((1+n)/(1+df)) + 1.
        self.idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0

        self.matrix = np.zeros((n_docs, vocab_size), dtype=float)
        for i, doc in enumerate(corpus_tokens):
            if not doc:
                continue
            for term, count in Counter(doc).items():
                j = self.vocab[term]
                self.matrix[i, j] = (count / len(doc)) * self.idf[j]
        self.matrix = self._l2_normalize(self.matrix)

    @staticmethod
    def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return matrix / norms

    def _vectorize_query(self, query_tokens: list[str]) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=float)
        if not query_tokens:
            return vec
        for term, count in Counter(query_tokens).items():
            j = self.vocab.get(term)
            if j is not None:
                vec[j] = (count / len(query_tokens)) * self.idf[j]
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        if self.matrix.size == 0:
            return np.zeros(self.matrix.shape[0], dtype=float)
        return self.matrix @ self._vectorize_query(query_tokens)


class HybridRetriever:
    def __init__(self, rrf_k: int = 60) -> None:
        self.rrf_k = rrf_k
        self._build()

    def _build(self) -> None:
        self.docs: list[dict[str, Any]] = document_store.get_all()
        corpus = [tokenize(d["title"] + " " + d["content"]) for d in self.docs]
        self.bm25 = OkapiBM25(corpus)
        self.tfidf = TfidfIndex(corpus)

    @staticmethod
    def _rank_map(scores: np.ndarray) -> dict[int, int]:
        """Map doc index -> 0-based rank (0 = best), ties broken deterministically."""
        order = np.argsort(-scores, kind="stable")
        return {int(idx): rank for rank, idx in enumerate(order)}

    def retrieve(self, query: str, top_k: int = 3) -> list[Citation]:
        if not self.docs:
            self._build()
        if not self.docs:
            return []

        q_tokens = tokenize(query)
        sparse = self.bm25.scores(q_tokens)
        dense = self.tfidf.scores(q_tokens)
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
