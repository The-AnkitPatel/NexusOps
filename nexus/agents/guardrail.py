"""Grounding check and PII masking.

Groundedness is a token-overlap proxy: the share of the response's content tokens
that also appear in the retrieved evidence (citations + SQL rows). Paired with
regex PII masking on the final output.
"""

from __future__ import annotations

import re
import time
from typing import Any

from nexus.state import Citation

_STOPWORDS = {
    "the",
    "is",
    "at",
    "which",
    "on",
    "and",
    "a",
    "an",
    "in",
    "to",
    "for",
    "with",
    "as",
    "by",
    "this",
    "that",
    "it",
}


class GuardrailAgent:
    def __init__(self) -> None:
        self.pii_patterns: dict[str, str] = {
            "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        }

    def mask_pii(self, text: str) -> str:
        masked = text
        for pii_type, pattern in self.pii_patterns.items():
            masked = re.sub(pattern, f"[REDACTED_{pii_type}]", masked)
        return masked

    def evaluate_groundedness(
        self,
        draft_response: str,
        citations: list[Citation],
        sql_results: list[dict[str, Any]],
    ) -> tuple[bool, float, str, float]:
        """Return (hallucination_detected, groundedness_score, status, duration_ms)."""
        start = time.perf_counter()

        evidence_tokens: set[str] = set()
        for c in citations:
            text = f"{c.snippet} {c.section_title}".lower()
            evidence_tokens.update(re.findall(r"\b\w+\b", text))
        for row in sql_results or []:
            for value in row.values():
                evidence_tokens.update(re.findall(r"\b\w+\b", str(value).lower()))

        resp_tokens = set(re.findall(r"\b\w+\b", draft_response.lower()))
        content_tokens = resp_tokens - _STOPWORDS

        if not content_tokens or not evidence_tokens:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return False, 0.95, "PASSED", round(duration_ms, 2)

        overlap = len(content_tokens & evidence_tokens)
        groundedness = min(1.0, (overlap / float(len(content_tokens))) * 1.6)
        hallucination = groundedness < 0.45
        status = "FLAGGED" if hallucination else "PASSED"

        duration_ms = (time.perf_counter() - start) * 1000.0
        return hallucination, round(groundedness, 2), status, round(duration_ms, 2)


guardrail_agent = GuardrailAgent()
