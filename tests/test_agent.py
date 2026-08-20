"""Offline tests for the stage-1 agent tools."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from agent import (
    calculate_change,
    calculate_ratio,
    classify_series,
    describe_limitation,
    finish_answer,
    graph_traversal,
    query_table,
    run_agent,
    run_investigation,
)
from jrkj.memory import TaskMemory
from jrkj.queries import query_shareholder_connections


class AgentToolTests(unittest.TestCase):
    def test_graph_tool_returns_period_and_source_evidence(self) -> None:
        result = graph_traversal(
            "common_shareholders", "000001.SZ", "000429.SZ", "", 3
        )
        self.assertGreater(result["count"], 0)
        self.assertTrue(all(item["period"] for item in result["evidence"]))
        self.assertTrue(all(
            item["source"].startswith("database/jrkj.sqlite3#shareholders:")
            for item in result["evidence"]
        ))

    def test_reverse_shareholder_connections(self) -> None:
        rows = query_shareholder_connections("600238.SH", "20260331", 10, 50)
        matches = {(row["s_holder_name"], row["s_info_windcode"]) for row in rows}
        self.assertIn(("北京燕赵汇金国际投资有限责任公司", "000955.SZ"), matches)
        self.assertTrue(all("shareholder_graph" in row["_source"] for row in rows))
    def test_query_financial_table_with_source(self) -> None:
        result = query_table(
            "financial_income",
            "920088.BJ",
            "range",
            "2026-03-31",
            "2026-03-31",
            ["oper_rev", "oper_profit"],
            1,
        )
        record = result["records"][0]
        self.assertAlmostEqual(record["oper_rev"], 53_400_311.43)
        self.assertIn("financial_income", record["_source"])
        evidence = result["evidence"][0]
        self.assertEqual(evidence["company"], "920088.BJ")
        self.assertEqual(evidence["period"], 20260331)
        self.assertEqual(evidence["source"], record["_source"])
        self.assertEqual(record["_statement_scope"], "母公司报表")

    def test_query_latest_announcement(self) -> None:
        result = query_table("announcements", "600238.SH", "latest", "", "", [], 1)
        self.assertIn("整改报告", result["records"][0]["n_info_title"])

    def test_query_multiple_periods_with_alias(self) -> None:
        result = query_table(
            "financial_income",
            "600238.SH",
            "range",
            "2024-01-01",
            "2025-12-31",
            ["revenue"],
            10,
        )
        self.assertEqual(len(result["records"]), 4)
        self.assertIn("oper_rev", result["records"][0])

    def test_latest_mode_ignores_model_supplied_dates(self) -> None:
        result = query_table(
            "financial_income",
            "600238.SH",
            "latest",
            "2023-01-01",
            "2023-01-01",
            ["revenue"],
            4,
        )
        self.assertEqual(len(result["records"]), 4)
        self.assertEqual(result["records"][0]["report_period"], 20251231)
        self.assertEqual(result["query_range"]["mode"], "latest")

    def test_common_financial_field_aliases(self) -> None:
        result = query_table(
            "financial_balance",
            "600238.SH",
            "range",
            "20251231",
            "20251231",
            ["report_date", "short_borrow"],
            1,
        )
        self.assertEqual(result["records"][0]["report_period"], 20251231)
        self.assertEqual(result["records"][0]["st_borrow"], 60_088_000)

    def test_limitation_has_citable_source(self) -> None:
        result = describe_limitation("consolidated_statement")
        self.assertIn("母公司报表", result["limitation"])
        self.assertIn("README.md#data-boundary", result["_source"])

    def test_ratio(self) -> None:
        result = calculate_ratio(25, 100, 100, "占比")
        self.assertEqual(result["value"], 25)

    def test_change_uses_absolute_start_as_denominator(self) -> None:
        result = calculate_change(-100, -50, "亏损变化")
        self.assertEqual(result["difference"], 50)
        self.assertEqual(result["percent_change"], 50)

    def test_series_marks_mixed_reporting_periods_not_comparable(self) -> None:
        result = classify_series(
            [20241231, 20250630, 20251231],
            [-68_993_092.03, -4_559_303.87, -8_713_696.22],
            "净利润",
        )
        self.assertFalse(result["comparable"])
        self.assertEqual(result["trend"], "not_comparable")
        self.assertEqual(result["raw_sequence_shape"], "fluctuating")

    def test_series_classifies_comparable_annual_values(self) -> None:
        result = classify_series([20231231, 20241231, 20251231], [1, 2, 3], "收入")
        self.assertTrue(result["comparable"])
        self.assertEqual(result["trend"], "increasing")

    def test_task_memory_deduplicates_evidence(self) -> None:
        memory = TaskMemory()
        result = query_table(
            "financial_income", "600238.SH", "range", "20251231", "20251231", ["oper_rev"], 1
        )
        memory.remember_query("first", result)
        memory.remember_query("second", result)
        self.assertEqual(memory.snapshot()["query_count"], 2)
        self.assertEqual(len(memory.snapshot()["evidence"]), 1)

    def test_finish_answer_schema(self) -> None:
        result = finish_answer(
            "结论",
            ["database/jrkj.sqlite3#financial_income:s_info_windcode=920088.BJ"],
            "high",
        )
        self.assertEqual(set(result), {"结论", "证据", "置信度"})

    def test_finish_answer_accepts_stringified_evidence_array(self) -> None:
        result = finish_answer(
            "结论",
            '["README.md#data-boundary:cross_table"]',
            "low",
        )
        self.assertEqual(result["证据"], ["README.md#data-boundary:cross_table"])

    def test_finish_answer_accepts_graph_and_document_sources(self) -> None:
        self.assertEqual(
            finish_answer("图路径", ["neo4j#ownership_graph:operation=paths"], "medium")["结论"],
            "图路径",
        )
        self.assertEqual(
            finish_answer("公告正文", ["document_graph#doc-1"], "high")["结论"],
            "公告正文",
        )

    def test_long_tool_text_is_marked_and_truncated(self) -> None:
        result = query_table(
            "research_reports",
            "601033.SH",
            "latest",
            "",
            "",
            ["abstract"],
            5,
        )
        record = next(item for item in result["records"] if item.get("abstract_truncated"))
        self.assertTrue(record["abstract_truncated"])
        self.assertLessEqual(len(record["abstract"]), 1500)

    def test_react_loop_query_then_finish(self) -> None:
        responses = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-query",
                        "type": "function",
                        "function": {
                            "name": "query_table",
                            "arguments": (
                                '{"table":"financial_income","windcode":"920088.BJ",'
                                '"date_mode":"range",'
                                '"start_date":"20260331","end_date":"20260331",'
                                '"fields":["oper_rev"],"limit":1}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-finish",
                        "type": "function",
                        "function": {
                            "name": "finish_answer",
                            "arguments": (
                                '{"conclusion":"营业收入为53400311.43元",'
                                '"evidence":["营业收入=53400311.43；来源：database/'
                                'jrkj.sqlite3#financial_income:s_info_windcode=920088.BJ,'
                                'report_period=20260331"],"confidence":"high"}'
                            ),
                        },
                    }
                ],
            },
        ]
        with patch("agent.call_deepseek", side_effect=responses):
            result = run_agent("营业收入是多少？", api_key="test-key")
        self.assertEqual(result["置信度"], "high")
        self.assertIn("53400311.43", result["结论"])

    def test_react_loop_allows_distinct_multi_table_queries(self) -> None:
        responses = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-income",
                        "type": "function",
                        "function": {
                            "name": "query_table",
                            "arguments": (
                                '{"table":"financial_income","windcode":"600238.SH",'
                                '"date_mode":"range","start_date":"20241231",'
                                '"end_date":"20251231","fields":["oper_rev"],"limit":10}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-cashflow",
                        "type": "function",
                        "function": {
                            "name": "query_table",
                            "arguments": (
                                '{"table":"financial_cashflow","windcode":"600238.SH",'
                                '"date_mode":"range","start_date":"20241231",'
                                '"end_date":"20251231",'
                                '"fields":["net_cash_flows_oper_act"],"limit":10}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-finish-multi",
                        "type": "function",
                        "function": {
                            "name": "finish_answer",
                            "arguments": (
                                '{"conclusion":"已完成跨表查询",'
                                '"evidence":["database/jrkj.sqlite3#financial_income:s_info_windcode=600238.SH",'
                                '"database/jrkj.sqlite3#financial_cashflow:s_info_windcode=600238.SH"],'
                                '"confidence":"medium"}'
                            ),
                        },
                    }
                ],
            },
        ]
        with patch("agent.call_deepseek", side_effect=responses):
            result = run_agent("比较收入和经营现金流", api_key="test-key")
        self.assertEqual(result["结论"], "已完成跨表查询")

    def test_react_loop_graph_tool_and_evidence_audit(self) -> None:
        responses = [
            {
                "role": "assistant", "content": "", "tool_calls": [{
                    "id": "call-graph", "type": "function", "function": {
                        "name": "graph_traversal",
                        "arguments": (
                            '{"operation":"common_shareholders","windcode":"000001.SZ",'
                            '"target_windcode":"000429.SZ","end_date":"", "max_hops":3}'
                        ),
                    },
                }],
            },
            {
                "role": "assistant", "content": "", "tool_calls": [{
                    "id": "call-finish-graph", "type": "function", "function": {
                        "name": "finish_answer",
                        "arguments": (
                            '{"conclusion":"发现待核实的同名股东线索",'
                            '"evidence":["database/jrkj.sqlite3#shareholders:"],'
                            '"confidence":"low"}'
                        ),
                    },
                }],
            },
        ]
        trace = []
        with patch("agent.call_deepseek", side_effect=responses), patch.dict("os.environ", {"JRKJ_GRAPH_MODE": "offline"}):
            result = run_agent("两家公司是否有共同股东？", api_key="test-key", trace=trace)
        self.assertEqual(result["置信度"], "low")
        self.assertTrue(any(item["event"] == "evidence_verification" for item in trace))

    def test_run_investigation_returns_audit_artifact(self) -> None:
        responses = [{
            "role": "assistant", "content": "", "tool_calls": [{
                "id": "call-limit-artifact", "type": "function", "function": {
                    "name": "describe_limitation", "arguments": '{"limitation":"unsupported"}',
                },
            }],
        }, {
            "role": "assistant", "content": "", "tool_calls": [{
                "id": "call-finish-artifact", "type": "function", "function": {
                    "name": "finish_answer", "arguments": (
                        '{"conclusion":"ok","evidence":["README.md#data-boundary:unsupported"],"confidence":"low"}'
                    ),
                },
            }],
        }]
        with patch("agent.call_deepseek", side_effect=responses):
            artifact = run_investigation("test", api_key="test-key")
        self.assertTrue(artifact.run_id)
        self.assertEqual(artifact.answer["结论"], "ok")


if __name__ == "__main__":
    unittest.main()
