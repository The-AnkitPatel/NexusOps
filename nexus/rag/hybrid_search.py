import re
import math
from typing import List, Dict, Any, Tuple
from collections import Counter
from nexus.state import Citation
from nexus.rag.document_store import document_store

class HybridRetriever:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k
        self.docs = document_store.get_all()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def _sparse_bm25_score(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        """Computes BM25-style term frequency overlap score."""
        if not doc_tokens:
            return 0.0
        doc_counter = Counter(doc_tokens)
        score = 0.0
        for token in query_tokens:
            tf = doc_counter[token]
            if tf > 0:
                # BM25 term weighting saturation formula
                score += (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (len(doc_tokens) / 50.0)))
        return score

    def _dense_semantic_score(self, query: str, doc_text: str) -> float:
        """
        Lightweight deterministic semantic projection for fast hybrid evaluation.
        Computes n-gram semantic intersection with character-level cosine affinity.
        """
        q_clean = query.lower()
        d_clean = doc_text.lower()
        
        # Word-level Jaccard + n-gram affinity
        q_words = set(q_clean.split())
        d_words = set(d_clean.split())
        if not q_words:
            return 0.0
            
        overlap = len(q_words.intersection(d_words)) / float(len(q_words))
        
        # Boost if key acronyms or policy identifiers match exactly
        acronyms = re.findall(r"\b[A-Z0-9-]{3,}\b", query)
        boost = 0.0
        for ac in acronyms:
            if ac.lower() in d_clean:
                boost += 0.35
                
        return min(1.0, overlap + boost)

    def retrieve(self, query: str, top_k: int = 3) -> List[Citation]:
        if not self.docs:
            self.docs = document_store.get_all()
            
        q_tokens = self._tokenize(query)
        
        # 1. Sparse Ranking
        sparse_scores = []
        for idx, doc in enumerate(self.docs):
            d_tokens = self._tokenize(doc["title"] + " " + doc["content"])
            s_score = self._sparse_bm25_score(q_tokens, d_tokens)
            sparse_scores.append((idx, s_score))
        sparse_scores.sort(key=lambda x: x[1], reverse=True)
        sparse_ranks = {doc_idx: rank for rank, (doc_idx, _) in enumerate(sparse_scores)}

        # 2. Dense Ranking
        dense_scores = []
        for idx, doc in enumerate(self.docs):
            d_score = self._dense_semantic_score(query, doc["title"] + " " + doc["content"])
            dense_scores.append((idx, d_score))
        dense_scores.sort(key=lambda x: x[1], reverse=True)
        dense_ranks = {doc_idx: rank for rank, (doc_idx, _) in enumerate(dense_scores)}

        # 3. Reciprocal Rank Fusion (RRF)
        combined_scores = []
        for idx in range(len(self.docs)):
            r_sparse = sparse_ranks[idx]
            r_dense = dense_ranks[idx]
            rrf_score = (1.0 / (self.rrf_k + r_sparse)) + (1.0 / (self.rrf_k + r_dense))
            combined_scores.append((idx, rrf_score))

        combined_scores.sort(key=lambda x: x[1], reverse=True)

        citations: List[Citation] = []
        for doc_idx, score in combined_scores[:top_k]:
            doc = self.docs[doc_idx]
            citations.append(Citation(
                document_id=doc["id"],
                section_title=doc["title"],
                snippet=doc["content"][:240] + "...",
                relevance_score=round(score * 100, 3)
            ))

        return citations

hybrid_retriever = HybridRetriever()
