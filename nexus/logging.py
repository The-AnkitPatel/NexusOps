"""Structured JSON logging for the gateway.

A single JSON-per-line handler on the ``nexus`` logger tree. JSON logs are the
norm for anything that ships to Cloud Logging / Loki, and they keep PII-masking
and trace correlation easy to reason about.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from nexus.config import settings

_configured = False


class JsonFormatter(logging.Formatter):
    """Render each log record as a compact JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("nexus")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger under the ``nexus`` namespace."""
    _configure()
    full = name if name.startswith("nexus") else f"nexus.{name}"
    return logging.getLogger(full)
