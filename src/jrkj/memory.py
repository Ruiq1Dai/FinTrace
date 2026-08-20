"""Task-scoped working memory for evidence-constrained agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class TaskMemory:
    query_signatures: Set[str] = field(default_factory=set)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    calculations: List[Dict[str, Any]] = field(default_factory=list)

    def remember_query(self, signature: str, result: Dict[str, Any]) -> None:
        self.query_signatures.add(signature)
        known = {item["source"] for item in self.evidence}
        for item in result.get("evidence", []):
            if item["source"] not in known:
                self.evidence.append(item)
                known.add(item["source"])

    def remember_calculation(self, tool: str, result: Dict[str, Any]) -> None:
        self.calculations.append({"tool": tool, "result": result})

    def snapshot(self) -> Dict[str, Any]:
        return {
            "query_count": len(self.query_signatures),
            "evidence": list(self.evidence),
            "calculations": list(self.calculations),
        }
