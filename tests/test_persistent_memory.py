"""Tests for the versioned evidence ledger."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent import query_table
from jrkj.database import DEFAULT_DB
from jrkj.persistent_memory import PersistentEvidenceMemory


class PersistentEvidenceMemoryTests(unittest.TestCase):
    def test_remember_and_recall_exact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = PersistentEvidenceMemory(Path(directory) / "memory.sqlite3", DEFAULT_DB)
            result = query_table(
                "financial_income", "600238.SH", "range",
                "20251231", "20251231", ["oper_rev"], 1,
            )
            self.assertEqual(memory.remember_query(result), 1)
            recalled = memory.recall("600238.SH", "financial_income", 10)
            self.assertEqual(len(recalled), 1)
            self.assertEqual(recalled[0]["values"]["oper_rev"], 328_367_159.64)
            self.assertEqual(recalled[0]["source"], result["evidence"][0]["source"])

    def test_repeated_evidence_is_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = PersistentEvidenceMemory(Path(directory) / "memory.sqlite3", DEFAULT_DB)
            result = query_table(
                "financial_cashflow", "600238.SH", "range",
                "20251231", "20251231", ["net_cash_flows_oper_act"], 1,
            )
            memory.remember_query(result)
            memory.remember_query(result)
            self.assertEqual(len(memory.recall("600238.SH", "financial_cashflow", 10)), 1)

    def test_same_source_merges_observed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = PersistentEvidenceMemory(Path(directory) / "memory.sqlite3", DEFAULT_DB)
            first = query_table(
                "financial_income", "600238.SH", "range",
                "20251231", "20251231", ["oper_rev"], 1,
            )
            second = query_table(
                "financial_income", "600238.SH", "range",
                "20251231", "20251231", ["net_profit_excl_min_int_inc"], 1,
            )
            memory.remember_query(first)
            memory.remember_query(second)
            recalled = memory.recall("600238.SH", "financial_income", 10)
            self.assertEqual(len(recalled), 1)
            self.assertEqual(set(recalled[0]["values"]), {"oper_rev", "net_profit_excl_min_int_inc"})


if __name__ == "__main__":
    unittest.main()
