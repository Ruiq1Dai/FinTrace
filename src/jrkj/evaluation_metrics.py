"""Metrics over InvestigationRun artifacts without changing annotations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def artifact_metrics(artifact: dict[str, Any]) -> dict[str, Any]:
    results = artifact.get("tool_results", [])
    calls = artifact.get("tool_calls", [])
    errors = 0
    for item in results:
        result = item.get("result", {}) if isinstance(item, dict) else {}
        if isinstance(result, dict) and result.get("error"):
            errors += 1
    sources = set(artifact.get("evidence_sources", []))
    answer = artifact.get("answer") or {}
    citations = answer.get("证据", []) if isinstance(answer, dict) else []
    unsupported = (artifact.get("verification") or {}).get("unsupported_citations", [])
    usage = artifact.get("token_usage") or {}
    return {
        "tool_call_count": len(calls),
        "tool_result_count": len(results),
        "tool_success_rate": (len(results) - errors) / len(results) if results else 0.0,
        "evidence_count": len(sources),
        "evidence_coverage": 1.0 if citations and not unsupported else (0.0 if citations else None),
        "unsupported_citation_count": len(unsupported),
        "run_error": bool(artifact.get("error")),
        "elapsed_ms": artifact.get("elapsed_ms"),
        "total_tokens": usage.get("total_tokens", 0),
    }


def load_metrics(artifacts_dir: str | Path) -> dict[str, Any]:
    paths = sorted(Path(artifacts_dir).glob("*.json"))
    rows = []
    for path in paths:
        try:
            rows.append({"id": path.stem, **artifact_metrics(json.loads(path.read_text(encoding="utf-8")))})
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            rows.append({"id": path.stem, "error": str(exc)})
    valid = [row for row in rows if "error" not in row]
    def average(key: str) -> float | None:
        values = [row[key] for row in valid if isinstance(row.get(key), (int, float))]
        return sum(values) / len(values) if values else None
    return {"count": len(rows), "valid_count": len(valid), "rows": rows,
            "averages": {key: average(key) for key in
                         ("tool_success_rate", "evidence_coverage", "elapsed_ms", "total_tokens")}}
