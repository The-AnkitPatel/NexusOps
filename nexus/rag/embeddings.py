"""Pluggable dense-embedding providers for the hybrid retriever.

The retriever's "dense" channel is defined by an :class:`EmbeddingProvider`:
- :class:`TfidfEmbedder` (default) — exact TF-IDF vectors on numpy, fully offline.
- :class:`GeminiEmbedder` — real neural embeddings via the Gemini API, used only
  when ``GEMINI_API_KEY`` is set; it degrades gracefully to TF-IDF otherwise.

Both return **L2-normalised** vectors, so cosine similarity is a plain dot product.
This keeps "swap in real embeddings" a one-line change behind a stable interface.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Protocol, runtime_checkable

import numpy as np

from nexus.config import settings
from nexus.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"\b\w+\b")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str

    def embed_documents(self, docs: list[str]) -> np.ndarray:
        """Return an (n_docs, dim) L2-normalised matrix."""
        ...

    def embed_query(self, query: str) -> np.ndarray:
        """Return a (dim,) L2-normalised vector in the same space."""
        ...


class TfidfEmbedder:
    """Exact TF-IDF vector space (sklearn-style smoothed idf), numpy only."""

    name = "tfidf"

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray = np.zeros(0, dtype=float)

    def embed_documents(self, docs: list[str]) -> np.ndarray:
        corpus = [tokenize(d) for d in docs]
        self.vocab = {}
        for tokens in corpus:
            for term in tokens:
                if term not in self.vocab:
                    self.vocab[term] = len(self.vocab)

        n_docs = len(corpus)
        vocab_size = len(self.vocab)
        df = np.zeros(vocab_size, dtype=float)
        for tokens in corpus:
            for term in set(tokens):
                df[self.vocab[term]] += 1.0
        self.idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0

        matrix = np.zeros((n_docs, vocab_size), dtype=float)
        for i, tokens in enumerate(corpus):
            if not tokens:
                continue
            for term, count in Counter(tokens).items():
                j = self.vocab[term]
                matrix[i, j] = (count / len(tokens)) * self.idf[j]
        return _l2_normalize(matrix)

    def embed_query(self, query: str) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=float)
        tokens = tokenize(query)
        if not tokens:
            return vec
        for term, count in Counter(tokens).items():
            j = self.vocab.get(term)
            if j is not None:
                vec[j] = (count / len(tokens)) * self.idf[j]
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec


class GeminiEmbedder:
    """Real neural embeddings via the Gemini API (key-gated, opt-in)."""

    name = "gemini"

    def __init__(self, model: str = "text-embedding-004") -> None:
        from google import genai  # raises ImportError if the [llm] extra is absent

        # Typed as Any: the optional google-genai stubs are brittle and this
        # adapter is exercised only when a real key is present.
        self._client: Any = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model = model

    def _embed(self, texts: list[str]) -> np.ndarray:
        resp = self._client.models.embed_content(model=self._model, contents=texts)
        rows: list[list[float]] = [list(e.values or []) for e in (resp.embeddings or [])]
        return _l2_normalize(np.asarray(rows, dtype=np.float64))

    def embed_documents(self, docs: list[str]) -> np.ndarray:
        return self._embed(list(docs))

    def embed_query(self, query: str) -> np.ndarray:
        return self._embed([query])[0]


def get_embedder() -> EmbeddingProvider:
    """Return the Gemini embedder when a key is configured, else TF-IDF."""
    if settings.GEMINI_API_KEY:
        try:
            embedder = GeminiEmbedder()
            logger.info("Dense channel: Gemini embeddings (%s)", embedder._model)
            return embedder
        except Exception as exc:
            logger.warning("Gemini embedder unavailable (%s); falling back to TF-IDF", exc)
    return TfidfEmbedder()
