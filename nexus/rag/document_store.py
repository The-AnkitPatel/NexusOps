import json
import os
from typing import List, Dict, Any

class DocumentStore:
    def __init__(self, json_path: str = "data/enterprise_policies.json"):
        self.json_path = json_path
        self.documents: List[Dict[str, Any]] = []
        self._load_documents()

    def _load_documents(self):
        if os.path.exists(self.json_path):
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
        else:
            self.documents = []

    def get_all(self) -> List[Dict[str, Any]]:
        return self.documents

document_store = DocumentStore()
