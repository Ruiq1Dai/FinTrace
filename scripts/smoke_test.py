#!/usr/bin/env python3
"""Machine-verifiable smoke checks.

The smoke path is deterministic and does not call an LLM. Neo4j is required
unless ``--skip-neo4j`` is explicitly supplied for an offline CI environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from agent import agent_graph_traversal, search_document_graph, scorecard_screen  # noqa: E402
from jrkj.risk_policy import classify_risk  # noqa: E402
from scripts.check_data import check_manifest  # noqa: E402


def run_smoke(skip_neo4j: bool = False) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    manifest = check_manifest(ROOT / "data" / "manifest.json")
    checks.append({"name": "data_contract", "ok": bool(manifest["complete"]), "detail": manifest})

    docs = search_document_graph("600238.SH", "行政监管措施", "announcement", 5)
    checks.append({"name": "document_graph", "ok": docs["count"] > 0 and all(item.get("sha256") for item in docs["records"]), "detail": {"count": docs["count"]}})

    score = scorecard_screen("piotroski_f", {key: True for key in ("roa_positive", "cfo_positive", "roa_improving", "accrual_quality", "leverage_improving", "liquidity_improving", "no_dilution", "margin_improving", "turnover_improving")})
    checks.append({"name": "deterministic_scorecard", "ok": bool(score["score"] == 9 and score["policy_version"]), "detail": score})

    risk = classify_risk(["revenue_cashflow", "receivables"], ["announcement_body"], comparable_periods=2)
    checks.append({"name": "risk_policy", "ok": risk["risk_code"] == "high" and risk["policy_version"] == "risk-policy-v1", "detail": risk})

    if skip_neo4j:
        checks.append({"name": "neo4j", "ok": True, "skipped": True, "detail": "explicit --skip-neo4j"})
    else:
        if not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_PASSWORD"):
            checks.append({"name": "neo4j", "ok": False, "detail": "NEO4J_URI and NEO4J_PASSWORD are required; use --skip-neo4j only for explicit offline CI"})
        else:
            graph = agent_graph_traversal(operation="paths", windcode="000001.SZ", target_windcode="600875.SH", end_date="20250331", max_hops=2)
            checks.append({"name": "neo4j", "ok": graph.get("backend") == "neo4j" and graph.get("count", 0) > 0 and all(item.get("source", "").startswith("neo4j#") for item in graph.get("evidence", [])), "detail": {"backend": graph.get("backend"), "count": graph.get("count")}})

    return {"ok": all(bool(check["ok"]) for check in checks), "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-neo4j", action="store_true")
    args = parser.parse_args()
    result = run_smoke(skip_neo4j=args.skip_neo4j)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
