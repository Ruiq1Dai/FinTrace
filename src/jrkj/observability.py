"""Small append-only run store for audit and observability."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class RunStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save(self, run: dict[str, Any] | Any) -> dict[str, Any]:
        payload = run.to_dict() if hasattr(run, "to_dict") else dict(run)
        if not payload.get("run_id"):
            raise ValueError("run_id is required")
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True) + "\n")
        return payload

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def get(self, run_id: str) -> dict[str, Any] | None:
        for row in reversed(self._read()):
            if row.get("run_id") == run_id:
                return row
        return None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(reversed(self._read()))[:max(1, min(int(limit), 100))]
