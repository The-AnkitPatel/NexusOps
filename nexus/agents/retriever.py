import time
from typing import List, Tuple
from nexus.rag.hybrid_search import hybrid_retriever
from nexus.state import Citation

class RetrieverAgent:
    def execute_retrieval(self, query: str, top_k: int = 2) -> Tuple[List[Citation], float]:
        start = time.time()
        citations = hybrid_retriever.retrieve(query, top_k=top_k)
        duration_ms = (time.time() - start) * 1000.0
        return citations, round(duration_ms, 2)

retriever_agent = RetrieverAgent()
