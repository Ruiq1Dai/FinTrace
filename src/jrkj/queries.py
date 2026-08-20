"""Small, dependency-free query helpers for the JRKJ SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence

from .database import DEFAULT_DB, normalize_date


FINANCIAL_TABLES = {
    "income": "financial_income",
    "balance": "financial_balance",
    "cashflow": "financial_cashflow",
}


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def select_rows(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[object],
) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def query_financial_statements(
    windcode: str,
    start_period: object | None = None,
    end_period: object | None = None,
    db_path: str | Path = DEFAULT_DB,
) -> dict[str, list[dict[str, Any]]]:
    """Return all three statements for one security, newest period first."""
    conditions = ["s_info_windcode = ?"]
    parameters: list[object] = [windcode.upper()]
    if start_period is not None:
        conditions.append("report_period >= ?")
        parameters.append(normalize_date(start_period))
    if end_period is not None:
        conditions.append("report_period <= ?")
        parameters.append(normalize_date(end_period))
    where = " AND ".join(conditions)

    with connect(db_path) as connection:
        return {
            name: select_rows(
                connection,
                f"SELECT * FROM {table} WHERE {where} ORDER BY report_period DESC, ann_dt DESC",
                parameters,
            )
            for name, table in FINANCIAL_TABLES.items()
        }


def query_top_shareholders(
    windcode: str,
    end_date: object | None = None,
    limit: int = 10,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    """Return shareholders for a date, or the latest available shareholder snapshot."""
    with connect(db_path) as connection:
        if end_date is None:
            row = connection.execute(
                "SELECT MAX(s_holder_enddate) FROM shareholders WHERE s_info_windcode = ?",
                (windcode.upper(),),
            ).fetchone()
            end_date = row[0] if row else None
        else:
            end_date = normalize_date(end_date)
        if end_date is None:
            return []
        return select_rows(
            connection,
            """
            SELECT * FROM shareholders
            WHERE s_info_windcode = ? AND s_holder_enddate = ?
            ORDER BY s_holder_pct DESC, s_holder_quantity DESC
            LIMIT ?
            """,
            (windcode.upper(), end_date, limit),
        )


def query_shareholder_connections(
    windcode: str,
    end_date: object | None = None,
    top_n: int = 10,
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    """Find other listed companies sharing exact-name top shareholders."""
    code = windcode.upper()
    holders = query_top_shareholders(code, end_date=end_date, limit=top_n, db_path=db_path)
    if not holders:
        return []
    names = [row["s_holder_name"] for row in holders if row.get("s_holder_name")]
    placeholders = ",".join("?" for _ in names)
    with connect(db_path) as connection:
        rows = select_rows(
            connection,
            f"""
            SELECT s_holder_name, s_info_windcode, s_holder_enddate, s_holder_pct
            FROM shareholders AS current
            WHERE s_holder_name IN ({placeholders})
              AND s_info_windcode <> ?
              AND s_holder_enddate = (
                  SELECT MAX(latest.s_holder_enddate)
                  FROM shareholders AS latest
                  WHERE latest.s_holder_name = current.s_holder_name
                    AND latest.s_info_windcode = current.s_info_windcode
              )
            ORDER BY s_holder_name, s_holder_pct DESC, s_info_windcode
            LIMIT ?
            """,
            [*names, code, max(1, min(int(limit), 200))],
        )
    anchor_pct = {row["s_holder_name"]: row.get("s_holder_pct") for row in holders}
    for row in rows:
        row["anchor_windcode"] = code
        row["anchor_holder_pct"] = anchor_pct.get(row["s_holder_name"])
        row["_source"] = (
            "database/jrkj.sqlite3#shareholder_graph:"
            f"holder={row['s_holder_name']},company={row['s_info_windcode']},"
            f"s_holder_enddate={row['s_holder_enddate']}"
        )
    return rows


def query_risk_announcements(
    windcode: str,
    start_date: object | None = None,
    end_date: object | None = None,
    limit: int = 20,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    """Return risk-announcement metadata, newest first."""
    conditions = ["s_info_windcode = ?"]
    parameters: list[object] = [windcode.upper()]
    if start_date is not None:
        conditions.append("ann_dt >= ?")
        parameters.append(normalize_date(start_date))
    if end_date is not None:
        conditions.append("ann_dt <= ?")
        parameters.append(normalize_date(end_date))
    parameters.append(limit)
    with connect(db_path) as connection:
        return select_rows(
            connection,
            f"""
            SELECT * FROM announcements
            WHERE {' AND '.join(conditions)}
            ORDER BY ann_dt DESC
            LIMIT ?
            """,
            parameters,
        )


def query_research_reports(
    windcode: str,
    start_date: object | None = None,
    end_date: object | None = None,
    limit: int = 20,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    """Return research-report metadata and abstracts, newest first."""
    conditions = ["s_info_windcode = ?"]
    parameters: list[object] = [windcode.upper()]
    if start_date is not None:
        conditions.append("publish_date >= ?")
        parameters.append(normalize_date(start_date))
    if end_date is not None:
        conditions.append("publish_date <= ?")
        parameters.append(normalize_date(end_date))
    parameters.append(limit)
    with connect(db_path) as connection:
        return select_rows(
            connection,
            f"""
            SELECT * FROM research_reports
            WHERE {' AND '.join(conditions)}
            ORDER BY publish_date DESC
            LIMIT ?
            """,
            parameters,
        )
