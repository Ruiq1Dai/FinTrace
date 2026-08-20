"""Deterministic, SQLite-backed ownership graph adapter.

The adapter keeps the existing shareholder schema as the source of truth. It
models shareholder-to-company edges for one snapshot and provides bounded
traversal suitable for evidence-producing tools. A graph database can be
added behind this interface later without changing callers.
"""

from __future__ import annotations

import sqlite3
from collections import deque
from pathlib import Path
from typing import Any

from .database import DEFAULT_DB, normalize_date


class OwnershipGraph:
    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB,
        end_date: object | None = None,
        include_all_periods: bool = False,
    ) -> None:
        self.db_path = Path(db_path)
        self.end_date = normalize_date(end_date) if end_date is not None else None
        self.include_all_periods = include_all_periods
        self._edges: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if self.include_all_periods:
                rows = conn.execute("SELECT * FROM shareholders").fetchall()
            elif self.end_date is None:
                rows = conn.execute(
                    "SELECT current.* FROM shareholders AS current "
                    "WHERE current.s_holder_enddate = ("
                    "SELECT MAX(latest.s_holder_enddate) FROM shareholders AS latest "
                    "WHERE latest.s_info_windcode = current.s_info_windcode)"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM shareholders WHERE s_holder_enddate = ?", (self.end_date,)
                ).fetchall()
        for row in rows:
            company = str(row["s_info_windcode"]).upper()
            holder = str(row["s_holder_name"] or "").strip()
            if not holder:
                continue
            self._edges.append({
                "holder": holder, "company": company,
                "pct": row["s_holder_pct"], "period": row["s_holder_enddate"],
                "source": f"shareholders:{company}:{holder}:{row['s_holder_enddate']}",
            })

    def _paths_from_edges(
        self,
        edges: list[dict[str, Any]],
        start: str,
        target: str,
        max_hops: int,
    ) -> list[list[dict[str, Any]]]:
        if max_hops < 1:
            raise ValueError("max_hops must be at least one")
        start, target = start.upper(), target.upper()
        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for edge in edges:
            company = f"company:{edge['company']}"
            holder = f"holder:{edge['holder']}"
            adjacency.setdefault(company, []).append((holder, edge))
            adjacency.setdefault(holder, []).append((company, edge))
        queue = deque([(f"company:{start}", [], {f"company:{start}"})])
        found: list[list[dict[str, Any]]] = []
        while queue:
            node, path, seen = queue.popleft()
            if len(path) >= max_hops:
                continue
            for nxt, edge in adjacency.get(node, []):
                if nxt in seen:
                    continue
                next_path = path + [edge]
                if nxt == f"company:{target}":
                    found.append(next_path)
                else:
                    queue.append((nxt, next_path, seen | {nxt}))
        return found

    def paths(self, start: str, target: str, max_hops: int = 3) -> list[list[dict[str, Any]]]:
        """Return bounded alternating holder/company paths with edge evidence."""
        return self._paths_from_edges(self._edges, start, target, max_hops)

    def common_shareholders(self, company_a: str, company_b: str) -> list[dict[str, Any]]:
        a, b = company_a.upper(), company_b.upper()
        left = {e["holder"]: e for e in self._edges if e["company"] == a}
        right = {e["holder"]: e for e in self._edges if e["company"] == b}
        return [{"holder": name, "company_a": left[name], "company_b": right[name]}
                for name in sorted(left.keys() & right.keys())]

    def snapshots(self) -> list[str]:
        """Return all available reporting dates in chronological order."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT s_holder_enddate FROM shareholders "
                "WHERE s_holder_enddate IS NOT NULL ORDER BY s_holder_enddate"
            ).fetchall()
        return [str(row[0]) for row in rows]

    def ultimate_controllers(self, company: str, max_hops: int = 6) -> list[dict[str, Any]]:
        """Find terminal holder candidates through company-to-company ownership edges.

        A shareholder name is treated as an intermediate company only when it
        exactly matches a company code present in the selected snapshot. Other
        names are terminal holder candidates. This is a graph traversal result,
        not a legal determination of control.
        """
        if max_hops < 1:
            raise ValueError("max_hops must be at least one")
        company = company.upper()
        by_company: dict[str, list[dict[str, Any]]] = {}
        for edge in self._edges:
            by_company.setdefault(edge["company"], []).append(edge)
        company_codes = set(by_company)
        queue = deque([(company, [], {company})])
        found: list[dict[str, Any]] = []
        while queue:
            node, path, seen = queue.popleft()
            if len(path) >= max_hops:
                continue
            for edge in by_company.get(node, []):
                current = path + [edge]
                holder = edge["holder"]
                intermediate = holder.upper()
                if intermediate in company_codes:
                    if intermediate not in seen:
                        queue.append((intermediate, current, seen | {intermediate}))
                else:
                    found.append({
                        "controller": holder,
                        "path": current,
                        "hops": len(current),
                        "candidate_type": "terminal_holder",
                    })
        # The same holder can be reachable through multiple edges; retain each
        # distinct source path because it is part of the audit evidence.
        return found

    def temporal_paths(self, start: str, target: str, max_hops: int = 3) -> dict[str, list[list[dict[str, Any]]]]:
        """Return paths independently for each shareholder snapshot."""
        grouped: dict[str, list[list[dict[str, Any]]]] = {}
        all_graph = OwnershipGraph(self.db_path, include_all_periods=True)
        edges_by_period: dict[str, list[dict[str, Any]]] = {}
        for edge in all_graph._edges:
            edges_by_period.setdefault(str(edge["period"]), []).append(edge)
        for period in sorted(edges_by_period):
            paths = all_graph._paths_from_edges(edges_by_period[period], start, target, max_hops)
            if paths:
                grouped[period] = paths
        return grouped

    def ownership_changes(self, company: str) -> list[dict[str, Any]]:
        """Compare holder entry, exit, and percentage changes across snapshots."""
        code = company.upper()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT s_holder_enddate, s_holder_name, s_holder_pct "
                "FROM shareholders WHERE s_info_windcode=? "
                "ORDER BY s_holder_enddate, s_holder_name",
                (code,),
            ).fetchall()
        snapshots: dict[int, dict[str, Any]] = {}
        for row in rows:
            snapshots.setdefault(int(row["s_holder_enddate"]), {})[row["s_holder_name"]] = row["s_holder_pct"]
        dates = sorted(snapshots)
        changes: list[dict[str, Any]] = []
        for previous_date, current_date in zip(dates, dates[1:]):
            previous, current = snapshots[previous_date], snapshots[current_date]
            for holder in sorted(set(previous) | set(current)):
                before, after = previous.get(holder), current.get(holder)
                if before == after:
                    continue
                changes.append({
                    "company": code,
                    "holder": holder,
                    "period_start": previous_date,
                    "period_end": current_date,
                    "status": "entered" if before is None else ("exited" if after is None else "changed"),
                    "pct_start": before,
                    "pct_end": after,
                    "source": f"database/jrkj.sqlite3#shareholders:company={code}:periods={previous_date},{current_date}",
                })
        return changes

    def circular_ownership(self, max_hops: int = 6) -> list[list[dict[str, Any]]]:
        """Find cycles in the derived company graph (companies sharing holders)."""
        if max_hops < 2:
            return []
        by_holder: dict[str, list[dict[str, Any]]] = {}
        for edge in self._edges:
            by_holder.setdefault(edge["holder"], []).append(edge)
        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for edges in by_holder.values():
            for left in edges:
                for right in edges:
                    if left["company"] != right["company"]:
                        adjacency.setdefault(left["company"], []).append((right["company"], right))
        cycles: list[list[dict[str, Any]]] = []
        for start in sorted(adjacency):
            queue = deque([(start, [], {start})])
            while queue:
                node, path, seen = queue.popleft()
                if len(path) >= max_hops:
                    continue
                for nxt, edge in adjacency.get(node, []):
                    if nxt == start and path:
                        candidate = path + [edge]
                        if candidate not in cycles:
                            cycles.append(candidate)
                    elif nxt not in seen:
                        queue.append((nxt, path + [edge], seen | {nxt}))
        return cycles
