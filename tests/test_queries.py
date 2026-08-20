"""Smoke tests against the generated JRKJ SQLite database."""

from __future__ import annotations

import sqlite3
import unittest

from jrkj.database import DEFAULT_DB
from jrkj.queries import (
    query_financial_statements,
    query_research_reports,
    query_risk_announcements,
    query_top_shareholders,
)


@unittest.skipUnless(DEFAULT_DB.exists(), "build the database before running query tests")
class QueryTests(unittest.TestCase):
    def test_database_counts_and_indexes(self) -> None:
        expected_counts = {
            "shareholders": 646_449,
            "announcements": 7_311,
            "financial_balance": 39_019,
            "financial_cashflow": 39_985,
            "financial_income": 38_210,
            "research_reports": 55_214,
        }
        with sqlite3.connect(DEFAULT_DB) as connection:
            actual = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in expected_counts
            }
            index_count = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index'"
            ).fetchone()[0]
        self.assertEqual(actual, expected_counts)
        self.assertEqual(index_count, 11)

    def test_financial_statements(self) -> None:
        result = query_financial_statements("920088.BJ", "2026-03-31", "2026-03-31")
        self.assertEqual({name: len(rows) for name, rows in result.items()}, {
            "income": 1,
            "balance": 1,
            "cashflow": 1,
        })
        self.assertAlmostEqual(result["income"][0]["oper_rev"], 53_400_311.43)

    def test_latest_shareholders(self) -> None:
        rows = query_top_shareholders("600238.SH", limit=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["s_holder_enddate"], 20260331)
        self.assertGreaterEqual(rows[0]["s_holder_pct"], rows[1]["s_holder_pct"])

    def test_risk_announcements(self) -> None:
        rows = query_risk_announcements("600238.SH", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertIn("整改报告", rows[0]["n_info_title"])

    def test_research_reports(self) -> None:
        rows = query_research_reports("601033.SH", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["s_info_windcode"], "601033.SH")
        self.assertTrue(rows[0]["abstract"])


if __name__ == "__main__":
    unittest.main()
