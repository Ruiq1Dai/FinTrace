"""Command-line interface for building and querying JRKJ data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database import DEFAULT_DB, build_database
from .queries import (
    query_financial_statements,
    query_research_reports,
    query_risk_announcements,
    query_top_shareholders,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jrkj")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-db", help="build the SQLite database")
    build.add_argument("--output", type=Path, default=DEFAULT_DB)
    build.add_argument("--force", action="store_true")

    query = subparsers.add_parser("query", help="query cleaned project data")
    query.add_argument(
        "kind", choices=["financial", "shareholders", "announcements", "reports"]
    )
    query.add_argument("windcode", help="Wind code, for example 600238.SH")
    query.add_argument("--start")
    query.add_argument("--end")
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--db", type=Path, default=DEFAULT_DB)
    return parser


def run_query(args: argparse.Namespace) -> object:
    if args.kind == "financial":
        return query_financial_statements(args.windcode, args.start, args.end, args.db)
    if args.kind == "shareholders":
        return query_top_shareholders(args.windcode, args.end, args.limit, args.db)
    if args.kind == "announcements":
        return query_risk_announcements(
            args.windcode, args.start, args.end, args.limit, args.db
        )
    return query_research_reports(args.windcode, args.start, args.end, args.limit, args.db)


def main() -> None:
    args = create_parser().parse_args()
    if args.command == "build-db":
        counts = build_database(args.output, args.force)
        print(f"Built {args.output.resolve()}")
        for table, count in counts.items():
            print(f"  {table}: {count:,} rows")
        return
    print(json.dumps(run_query(args), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
