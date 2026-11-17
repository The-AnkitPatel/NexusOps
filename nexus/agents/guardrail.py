import re
import time
from typing import Tuple, List, Dict, Any
from nexus.state import Citation

class GuardrailAgent:
    def __init__(self):
        # Regex patterns for enterprise data protection
        self.pii_patterns = {
            "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        }

    def mask_pii(self, text: str) -> str:
        masked = text
        for pii_type, pattern in self.pii_patterns.items():
            masked = re.sub(pattern, f"[REDACTED_{pii_type}]", masked)
        return masked

    def evaluate_groundedness(
        self,
        draft_response: str,
        citations: List[Citation],
        sql_results: List[Dict[str, Any]]
    ) -> Tuple[bool, float, str, float]:
        """
        Calculates factual grounding against context evidence.
        Returns: (hallucination_detected, groundedness_score, guardrail_status, duration_ms)
        """
        start = time.time()
        
        # Build ground-truth token bag
        evidence_tokens = set()
        for c in citations:
            evidence_tokens.update(re.findall(r"\b\w+\b", (c.snippet + " " + c.section_title).lower()))
            
        for row in (sql_results or []):
            for k, v in row.items():
                evidence_tokens.update(re.findall(r"\b\w+\b", str(v).lower()))

        resp_tokens = set(re.findall(r"\b\w+\b", draft_response.lower()))
        
        # Drop common stop words
        stopwords = {"the", "is", "at", "which", "on", "and", "a", "an", "in", "to", "for", "with", "as", "by", "this", "that", "it"}
        content_tokens = resp_tokens - stopwords
        
        if not content_tokens or not evidence_tokens:
            duration_ms = (time.time() - start) * 1000.0
            return False, 0.95, "PASSED", round(duration_ms, 2)

        overlap = len(content_tokens.intersection(evidence_tokens))
        groundedness = min(1.0, (overlap / float(len(content_tokens))) * 1.6)
        
        # Check threshold
        hallucination = groundedness < 0.45
        status = "FLAGGED" if hallucination else "PASSED"
        
        duration_ms = (time.time() - start) * 1000.0
        return hallucination, round(groundedness, 2), status, round(duration_ms, 2)

guardrail_agent = GuardrailAgent()
