#!/usr/bin/env python3
"""Build the auditable entity master for the selected demo cases.

The local dataset provides reliable security codes and shareholder names, but
does not provide enough evidence to resolve every holder to a legal entity.
This generator therefore records unresolved names explicitly instead of
guessing aliases or control relationships.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ("600238.SH", "601033.SH", "300838.SZ")


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def build_entity_master(sqlite_path: Path, cases: tuple[str, ...] = DEFAULT_CASES, holder_limit: int = 10) -> list[dict[str, Any]]:
    if holder_limit < 1:
        raise ValueError("holder_limit must be positive")
    records: list[dict[str, Any]] = []
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        for code in cases:
            code = code.upper().strip()
            names = [
                row["sec_name"]
                for row in connection.execute(
                    "SELECT sec_name FROM research_reports WHERE s_info_windcode=? "
                    "AND sec_name IS NOT NULL AND trim(sec_name)<>'' ORDER BY publish_date DESC LIMIT 1",
                    (code,),
                )
                if row["sec_name"]
            ]
            latest_row = connection.execute(
                "SELECT max(s_holder_enddate) AS period FROM shareholders WHERE s_info_windcode=?",
                (code,),
            ).fetchone()
            period = str(latest_row["period"]) if latest_row and latest_row["period"] is not None else None
            records.append({
                "entity_id": f"security:{code}",
                "entity_type": "company",
                "security_code": code,
                "canonical_name": names[0] if names else None,
                "aliases": [code] + ([names[0]] if names else []),
                "verification_status": "verified_security_code",
                "effective_period": period,
                "source": f"database/jrkj.sqlite3#research_reports:{code}" if names else f"database/jrkj.sqlite3#shareholders:{code}",
            })
            if period is None:
                continue
            holders = connection.execute(
                "SELECT s_holder_name, s_holder_pct, s_holder_sequence FROM shareholders "
                "WHERE s_info_windcode=? AND s_holder_enddate=? AND s_holder_name IS NOT NULL "
                "ORDER BY s_holder_sequence, s_holder_name LIMIT ?",
                (code, int(period), holder_limit),
            ).fetchall()
            for row in holders:
                holder = str(row["s_holder_name"]).strip()
                records.append({
                    "entity_id": _stable_id("holder", holder),
                    "entity_type": "holder",
                    "canonical_name": holder,
                    "aliases": [holder],
                    "verification_status": "unresolved_name_match",
                    "company_scope": [code],
                    "effective_period": period,
                    "observed_ownership_pct": row["s_holder_pct"],
                    "source": f"database/jrkj.sqlite3#shareholders:{code}:{period}",
                    "limitations": ["Name-only record; no legal-entity or beneficial-owner resolution performed"],
                })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=ROOT / "database" / "jrkj.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "enriched" / "entity_master.jsonl")
    parser.add_argument("--holder-limit", type=int, default=10)
    args = parser.parse_args()
    records = build_entity_master(args.sqlite, holder_limit=args.holder_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "records": len(records), "verified_companies": sum(r["entity_type"] == "company" for r in records), "unresolved_holders": sum(r["verification_status"] == "unresolved_name_match" for r in records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
