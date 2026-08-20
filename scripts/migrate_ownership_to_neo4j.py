#!/usr/bin/env python3
"""Import the current SQLite shareholder snapshot into Neo4j."""
from __future__ import annotations
import argparse
import os
import sqlite3
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph
from jrkj.entity_resolution import load_resolutions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, default=ROOT / "database" / "jrkj.sqlite3")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--entities", type=Path, default=ROOT / "data" / "enriched" / "entity_master.jsonl")
    parser.add_argument("--resolutions", type=Path, default=ROOT / "data" / "enriched" / "entity_resolutions.jsonl")
    args = parser.parse_args()
    if not args.password:
        parser.error("--password or NEO4J_PASSWORD is required")
    with sqlite3.connect(args.sqlite) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT s_info_windcode, s_holder_name, s_holder_pct, s_holder_enddate FROM shareholders").fetchall()
    edges = [{"company": str(row["s_info_windcode"]).upper(), "holder": str(row["s_holder_name"]).strip(),
              "pct": row["s_holder_pct"], "period": str(row["s_holder_enddate"]),
              "source": f"shareholders:{row['s_info_windcode']}:{row['s_holder_name']}:{row['s_holder_enddate']}"}
             for row in rows if row["s_holder_name"]]
    graph = Neo4jOwnershipGraph(args.uri, args.user, args.password, args.database)
    try:
        graph.ensure_schema()
        print(f"Imported {graph.upsert_edges(edges, batch_size=args.batch_size)} ownership edges")
        if args.entities.is_file():
            records = [json.loads(line) for line in args.entities.read_text(encoding="utf-8").splitlines() if line.strip()]
            print(f"Imported {graph.upsert_entities(records, batch_size=args.batch_size)} entity records")
        resolutions = load_resolutions(args.resolutions)
        if resolutions:
            print(f"Imported {graph.upsert_resolutions(resolutions, batch_size=args.batch_size)} resolved entity edges")
    finally:
        graph.close()


if __name__ == "__main__":
    main()
