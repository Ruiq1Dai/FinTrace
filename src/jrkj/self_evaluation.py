"""Generate -> Verify -> Repair checks for investigation artifacts."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

from .evidence_verifier import verify_citations


def evaluate_artifact(answer: dict[str, Any], evidence_sources: list[str], tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    verification = verify_citations(answer, evidence_sources)
    claims = answer.get("claims", answer.get("结论", []))
    if isinstance(claims, str):
        claims = [claims]
    numeric_claims = sum(any(ch.isdigit() for ch in str(claim)) for claim in claims)
    formulas = sum(bool(isinstance(item.get("result"), dict) and item["result"].get("formula")) for item in tool_results)
    return {"valid": verification["valid"], "citation": verification, "claim_count": len(claims),
            "numeric_claim_count": numeric_claims, "calculation_result_count": formulas,
            "unsupported_claim_rate": 0.0 if not claims else round(len(verification["unsupported_citations"]) / len(claims), 6),
            "repair_required": not verification["valid"]}


def repair_artifact(answer: dict[str, Any], evidence_sources: list[str]) -> dict[str, Any]:
    """Remove only citations not observed in this run and lower confidence.

    Repair never invents a source or changes the substantive conclusion. If all
    citations are unsupported, the caller must send the model back through the
    tool loop instead of returning an unevidenced answer.
    """
    candidate = deepcopy(answer)
    citations = candidate.get("证据", [])
    if isinstance(citations, str):
        citations = [citations]
    known = sorted({source for source in evidence_sources if source})
    supported = [citation for citation in citations if any(citation in source or source in citation for source in known)]
    unsupported = [citation for citation in citations if citation not in supported]
    if unsupported:
        candidate["证据"] = supported
        if candidate.get("置信度") == "high":
            candidate["置信度"] = "medium"
    return {
        "answer": candidate if supported else None,
        "removed_citations": unsupported,
        "remaining_citations": supported,
        "actions": ["removed_unsupported_citations", "lowered_confidence"] if unsupported and supported else [],
        "repairable": bool(supported),
    }
