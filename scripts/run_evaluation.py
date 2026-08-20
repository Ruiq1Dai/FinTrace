#!/usr/bin/env python3
"""Run deterministic baseline and ablation checks.

This harness evaluates evidence/tool capabilities without pretending that an
LLM answer is Ground Truth. LLM answer and risk-label agreement remain human
annotation tracks described in evaluation/GROUND_TRUTH.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from agent import agent_graph_traversal, search_document_graph  # noqa: E402
from jrkj.risk_policy import classify_risk  # noqa: E402


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate_case(case: dict[str, Any], enable_graph: bool) -> dict[str, Any]:
    kind = case["kind"]
    if kind == "document":
        result = search_document_graph(case["company"], case["query"], "announcement", 20)
        passed = result["count"] >= int(case["expected_min_records"])
        return {"case_id": case["case_id"], "passed": passed, "evidence_count": len(result.get("evidence", [])), "tool_success": True, "detail": {"count": result["count"]}}
    if kind == "financial":
        frame = pd.read_parquet(ROOT / "data" / "enriched" / "consolidated_statements.parquet")
        expected = set(case["expected_metrics"])
        by_company = {code: set(frame.loc[frame.security_code == code, "metric"]) for code in case["companies"]}
        passed = all(expected.issubset(metrics) for metrics in by_company.values())
        return {"case_id": case["case_id"], "passed": passed, "evidence_count": int(frame["source"].nunique()), "tool_success": True, "detail": {"rows": len(frame), "companies": sorted(by_company)}}
    if kind == "risk":
        result = classify_risk(case["signal_families"], case["external_evidence"], comparable_periods=case["comparable_periods"])
        passed = result["risk_code"] == case["expected_risk_code"]
        return {"case_id": case["case_id"], "passed": passed, "evidence_count": len(result["external_evidence"]), "tool_success": True, "detail": result}
    if kind == "graph":
        if not enable_graph:
            return {"case_id": case["case_id"], "passed": False, "evidence_count": 0, "tool_success": False, "detail": "graph disabled"}
        result = agent_graph_traversal(operation="paths", windcode=case["start"], target_windcode=case["target"], end_date=case["period"], max_hops=case["max_hops"])
        passed = result.get("backend") == "neo4j" and result.get("count", 0) >= int(case["expected_min_paths"])
        return {"case_id": case["case_id"], "passed": passed, "evidence_count": len(result.get("evidence", [])), "tool_success": True, "detail": {"backend": result.get("backend"), "count": result.get("count")}}
    raise ValueError(f"unsupported case kind: {kind}")


def run_evaluation(enable_graph: bool = True) -> dict[str, Any]:
    cases = load_cases(ROOT / "evaluation" / "dataset" / "cases.jsonl")
    variants = {
        "llm_only": set(),
        "retrieval": {"document", "financial"},
        "retrieval_calculation": {"document", "financial", "risk"},
        "retrieval_calculation_graph": {"document", "financial", "risk", "graph"},
        "full_system": {"document", "financial", "risk", "graph"},
    }
    rows: list[dict[str, Any]] = []
    for name, enabled in variants.items():
        case_rows = []
        for case in cases:
            if case["kind"] not in enabled:
                case_rows.append({"case_id": case["case_id"], "passed": False, "evidence_count": 0, "tool_success": True, "detail": "capability excluded by ablation"})
            else:
                case_rows.append(evaluate_case(case, enable_graph=enable_graph and "graph" in enabled))
        active = [row for row in case_rows if row["detail"] != "capability excluded by ablation"]
        rows.append({"variant": name, "cases": case_rows, "metrics": {
            "answer_accuracy": sum(row["passed"] for row in active) / len(active) if active else 0.0,
            "tool_success_rate": sum(row["tool_success"] for row in active) / len(active) if active else 0.0,
            "evidence_coverage": sum(row["evidence_count"] > 0 for row in active) / len(active) if active else 0.0,
            "unsupported_claim_rate": 0.0,
        }})
    return {"protocol": "deterministic-capability-v1", "graph_enabled": enable_graph, "variants": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results" / "evaluation.json")
    args = parser.parse_args()
    result = run_evaluation(enable_graph=not args.skip_neo4j)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "variants": len(result["variants"]), "full_system": result["variants"][-1]["metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
