"""Tests for bounded long-context packing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent import query_table
from jrkj.context import ContextBuilder
from jrkj.database import DEFAULT_DB
from jrkj.persistent_memory import PersistentEvidenceMemory


class ContextBuilderTests(unittest.TestCase):
    def test_context_is_company_scoped_and_source_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = PersistentEvidenceMemory(Path(directory) / "memory.sqlite3", DEFAULT_DB)
            memory.remember_query(query_table(
                "financial_income", "600238.SH", "range", "20251231", "20251231",
                ["oper_rev"], 1,
            ))
            context = ContextBuilder(memory).build("600238.SH 的营业收入是多少？", 1000)
            self.assertEqual(context["company"], "600238.SH")
            self.assertEqual(context["fact_count"], 1)
            self.assertIn("database/jrkj.sqlite3#financial_income", context["context_text"])

    def test_context_budget_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = PersistentEvidenceMemory(Path(directory) / "memory.sqlite3", DEFAULT_DB)
            for period in (20231231, 20241231, 20250630, 20251231):
                memory.remember_query(query_table(
                    "financial_income", "600238.SH", "range", str(period), str(period),
                    ["oper_rev", "net_profit_excl_min_int_inc"], 1,
                ))
            context = ContextBuilder(memory).build("600238.SH 的收入和利润趋势", 100)
            self.assertLessEqual(len(context["context_text"]), 400)


if __name__ == "__main__":
    unittest.main()
