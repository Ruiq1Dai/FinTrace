"""Serializable audit artifact for one Agent investigation run."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class InvestigationRun:
    run_id: str
    question: str
    started_at: float
    answer: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    calculations: list[dict[str, Any]] = field(default_factory=list)
    verification: dict[str, Any] | None = None
    self_evaluation: dict[str, Any] | None = None
    elapsed_ms: float | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    retries: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_trace(
        cls,
        question: str,
        trace: list[dict[str, Any]],
        answer: dict[str, Any] | None = None,
        run_id: str | None = None,
        started_at: float | None = None,
    ) -> "InvestigationRun":
        artifact = cls(run_id or str(uuid.uuid4()), question, started_at or time.time(), answer)
        prompt_tokens = completion_tokens = total_tokens = 0
        plan_names: list[str] = []
        for event in trace:
            if event.get("event") == "model_response":
                artifact.tool_calls.extend(event.get("tool_calls") or [])
                for call in event.get("tool_calls") or []:
                    name = call.get("function", {}).get("name")
                    if name and name not in plan_names:
                        plan_names.append(name)
                usage = event.get("usage") or {}
                prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                total_tokens += int(usage.get("total_tokens", 0) or 0)
            elif event.get("event") == "tool_result":
                result = event.get("result")
                artifact.tool_results.append({"tool": event.get("tool"), "result": result})
                if isinstance(result, dict):
                    source = result.get("_source")
                    if isinstance(source, str):
                        artifact.evidence_sources.append(source)
                    for item in result.get("evidence", []):
                        if isinstance(item, dict) and isinstance(item.get("source"), str):
                            artifact.evidence_sources.append(item["source"])
                    if result.get("formula") or result.get("signals"):
                        artifact.calculations.append(result)
            elif event.get("event") == "evidence_verification":
                artifact.verification = event.get("result")
            elif event.get("event") == "self_evaluation":
                artifact.self_evaluation = event.get("result")
            elif event.get("event") == "error":
                artifact.errors.append({"tool": event.get("tool"), "message": event.get("message")})
            elif event.get("event") == "retry":
                artifact.retries += 1
        artifact.evidence_sources = sorted(set(artifact.evidence_sources))
        artifact.plan = [{"step": index, "tool": name} for index, name in enumerate(plan_names, 1)]
        artifact.elapsed_ms = round(max(0.0, (time.time() - artifact.started_at) * 1000), 3)
        artifact.token_usage = {"prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens}
        return artifact

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str, sort_keys=True)
