"""Dependency-light analyze service boundary.

The function is framework agnostic so CLI, a future HTTP server, and the
frontend can share the same response contract without a migration.
"""

from __future__ import annotations

from typing import Any, Callable

from .investigation_run import InvestigationRun


def analyze_question(
    question: str,
    runner: Callable[..., InvestigationRun],
    **runner_kwargs: Any,
) -> dict[str, Any]:
    """Run one investigation and return a JSON-compatible response envelope."""
    if not isinstance(question, str) or not question.strip():
        return {"ok": False, "error": {"code": "invalid_question", "message": "question is required"}}
    try:
        artifact = runner(question.strip(), **runner_kwargs)
        if not isinstance(artifact, InvestigationRun):
            raise TypeError("runner must return InvestigationRun")
        return {"ok": True, "run": artifact.to_dict()}
    except Exception as exc:  # Service boundary must return structured errors.
        return {"ok": False, "error": {"code": "investigation_failed", "message": str(exc)}}
