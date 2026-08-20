"""Deterministic verification of final-answer citations."""

from __future__ import annotations

from typing import Any, Iterable


def verify_citations(answer: dict[str, Any], known_sources: Iterable[str]) -> dict[str, Any]:
    """Require citations to originate from sources observed in the current run."""
    sources = sorted({source for source in known_sources if source})
    citations = answer.get("证据", [])
    missing = [
        citation for citation in citations
        if not any(citation in source or source in citation for source in sources)
    ]
    return {
        "valid": not missing,
        "citation_count": len(citations),
        "known_source_count": len(sources),
        "unsupported_citations": missing,
    }
