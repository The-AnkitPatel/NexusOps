"""Loads the enterprise policy corpus from JSON into memory."""

from __future__ import annotations

import json
import os
from typing import Any

from nexus.config import settings


class DocumentStore:
    def __init__(self, json_path: str | None = None) -> None:
        self.json_path = json_path or settings.POLICIES_PATH
        self.documents: list[dict[str, Any]] = []
        self._load_documents()

    def _load_documents(self) -> None:
        if os.path.exists(self.json_path):
            with open(self.json_path, encoding="utf-8") as f:
                self.documents = json.load(f)
        else:
            self.documents = []

    def get_all(self) -> list[dict[str, Any]]:
        return self.documents


document_store = DocumentStore()
