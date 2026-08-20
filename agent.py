#!/usr/bin/env python3
"""Evidence-constrained ReAct agent for the JRKJ SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from jrkj.database import DEFAULT_DB, normalize_date
from jrkj.queries import query_shareholder_connections
from jrkj.calculations import calculate_change, classify_series
from jrkj.evidence import Evidence
from jrkj.memory import TaskMemory
from jrkj.persistent_memory import PersistentEvidenceMemory
from jrkj.context import ContextBuilder
from jrkj.evidence_verifier import verify_citations
from jrkj.risk_signals import financial_risk_signals, financial_risk_signals_from_records
from jrkj.advanced_scores import beneish_m_score, altman_z_score, piotroski_f_score, peer_zscore
from jrkj.risk_policy import classify_risk
from jrkj.document_graph import DocumentGraph
from jrkj.investigation_run import InvestigationRun
from jrkj.ownership_graph import OwnershipGraph
from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph
from jrkj.self_evaluation import evaluate_artifact, repair_artifact


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/beta").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-v4-flash")
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "high")
API_URL = f"{LLM_BASE_URL}/chat/completions"
GRAPH_MODE = os.getenv("JRKJ_GRAPH_MODE", "neo4j").strip().lower()
# Allow a complete three-statement workflow: reads, deterministic calculations, and synthesis.
MAX_STEPS = 10
MAX_DATA_CALLS = 8
MAX_TOOL_TEXT_CHARS = 1500

TABLES = {
    "financial_income": {
        "time": "report_period",
        "default_fields": ["oper_rev", "oper_profit", "net_profit_excl_min_int_inc"],
    },
    "financial_balance": {
        "time": "report_period",
        "default_fields": ["monetary_cap", "acct_rcv", "inventories", "tot_assets", "tot_liab"],
    },
    "financial_cashflow": {
        "time": "report_period",
        "default_fields": [
            "net_cash_flows_oper_act",
            "net_cash_flows_inv_act",
            "net_cash_flows_fnc_act",
        ],
    },
    "shareholders": {
        "time": "s_holder_enddate",
        "default_fields": ["s_holder_name", "s_holder_quantity", "s_holder_pct"],
    },
    "announcements": {
        "time": "ann_dt",
        "default_fields": ["n_info_title", "n_info_fcode", "n_info_annlink"],
    },
    "research_reports": {
        "time": "publish_date",
        "default_fields": ["org_name", "title", "rating_org", "abstract"],
    },
}

FIELD_ALIASES = {
    "financial_income": {
        "report_date": "report_period",
        "revenue": "oper_rev",
        "operating_revenue": "oper_rev",
        "net_profit": "net_profit_excl_min_int_inc",
        "investment_income": "plus_net_invest_inc",
        "fair_value_change": "plus_net_gain_chg_fv",
    },
    "financial_balance": {
        "report_date": "report_period",
        "cash": "monetary_cap",
        "accounts_receivable": "acct_rcv",
        "inventory": "inventories",
        "short_term_borrowing": "st_borrow",
        "short_loan": "st_borrow",
        "short_borrow": "st_borrow",
    },
    "financial_cashflow": {
        "report_date": "report_period",
        "operating_cash_flow": "net_cash_flows_oper_act",
    },
}

LIMITATIONS = {
    "announcement_body": "公告数据只有标题、分类和PDF链接，没有正文，不能回答具体原因或责任人。",
    "control_chain": "股东数据只有前十大股东快照，没有实际控制人字段和多层控制链。",
    "consolidated_statement": "当前财务记录为母公司报表口径，不含合并报表。",
    "unsupported": "当前数据或工具不足以可靠回答该问题。",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "financial_risk_signals",
            "strict": True,
            "description": "Compute deterministic financial anomaly screening signals. Signals are leads, not fraud conclusions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periods": {"type": "array", "items": {"type": "integer"}},
                    "revenue": {"type": "array", "items": {"type": ["number", "null"]}},
                    "operating_cash_flow": {"type": "array", "items": {"type": ["number", "null"]}},
                    "receivables": {"type": "array", "items": {"type": ["number", "null"]}},
                    "inventory": {"type": "array", "items": {"type": ["number", "null"]}},
                },
                "required": ["periods", "revenue", "operating_cash_flow", "receivables", "inventory"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "financial_risk_signals_from_records",
            "strict": True,
            "description": "Align previously queried income, cashflow and optional balance records by report_period and attach source citations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "income_records": {"type": "array", "items": {"type": "object"}},
                    "cashflow_records": {"type": "array", "items": {"type": "object"}},
                    "balance_records": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["income_records", "cashflow_records", "balance_records"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scorecard_screen",
            "strict": True,
            "description": "Run one deterministic financial scorecard. Scores are screening signals, not fraud or solvency findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "enum": ["beneish_m", "altman_z", "piotroski_f", "peer_z"]},
                    "values": {"type": "object", "additionalProperties": True},
                },
                "required": ["model", "values"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_risk",
            "strict": True,
            "description": "Apply risk-policy-v1 to independent signal families and evidence categories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_families": {"type": "array", "items": {"type": "string"}},
                    "external_evidence": {"type": "array", "items": {"type": "string"}},
                    "data_sufficient": {"type": "boolean"},
                    "comparable_periods": {"type": "integer", "minimum": 0},
                    "official_finding": {"type": "boolean"},
                },
                "required": ["signal_families", "external_evidence", "data_sufficient", "comparable_periods", "official_finding"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_traversal",
            "strict": True,
            "description": "Deterministic top-shareholder graph traversal; matches are clues, not proof of control.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["common_shareholders", "paths", "cycles", "controllers"]},
                    "windcode": {"type": "string"},
                    "target_windcode": {"type": "string"},
                    "end_date": {"type": "string"},
                    "max_hops": {"type": "integer", "minimum": 1, "maximum": 6},
                },
                "required": ["operation", "windcode", "target_windcode", "end_date", "max_hops"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_evidence_memory",
            "strict": True,
            "description": (
                "Recall exact previously observed evidence for a company from the versioned "
                "evidence ledger. Returned records retain their original database source; "
                "use this only for reuse, never as a replacement for missing data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "windcode": {"type": "string"},
                    "table": {"type": "string", "enum": list(TABLES) + [""]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["windcode", "table", "limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_document_graph",
            "strict": True,
            "description": "Search the enriched announcement/research document graph and return source-preserving excerpts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "windcode": {"type": "string"},
                    "query": {"type": "string"},
                    "kind": {"type": "string", "enum": ["", "announcement", "research"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["windcode", "query", "kind", "limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_shareholder_connections",
            "strict": True,
            "description": (
                "Find exact-name shareholders from one company's latest or specified top-holder "
                "snapshot that also appear in other listed companies. Same names are clues only, "
                "not proof of identity, control, or related-party relationships."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "windcode": {"type": "string"},
                    "end_date": {"type": "string", "description": "YYYYMMDD/date or empty for latest"},
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 10},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200}
                },
                "required": ["windcode", "end_date", "top_n", "limit"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_table",
            "strict": True,
            "description": (
                "Query one JRKJ table for one security. A task may query multiple different "
                "periods: set date_mode=latest and limit=N for the latest N records, or "
                "date_mode=range for dates explicitly stated in the question. Never invent dates. "
                "You may query multiple tables, but avoid repeating an identical query. Common fields: income oper_rev/oper_profit/"
                "net_profit_excl_min_int_inc/plus_net_invest_inc/plus_net_gain_chg_fv/statement_type; balance monetary_cap/acct_rcv/inventories/st_borrow/"
                "tot_assets/tot_liab; cashflow net_cash_flows_oper_act; shareholders "
                "s_holder_name/s_holder_pct; announcements n_info_title/n_info_annlink; "
                "reports title/abstract/rating_org."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "enum": list(TABLES)},
                    "windcode": {
                        "type": "string",
                        "description": "Wind code with exchange suffix, e.g. 600238.SH",
                    },
                    "date_mode": {
                        "type": "string",
                        "enum": ["latest", "range"],
                        "description": "Use latest unless the question explicitly states dates",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Inclusive YYYY-MM-DD/YYYYMMDD, or empty for latest",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Inclusive YYYY-MM-DD/YYYYMMDD, or empty for latest",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Requested columns, or an empty array for defaults",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": [
                    "table", "windcode", "date_mode", "start_date", "end_date", "fields", "limit"
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_ratio",
            "strict": True,
            "description": "Calculate numerator / denominator after obtaining values from one or more tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "numerator": {"type": "number"},
                    "denominator": {"type": "number"},
                    "scale": {"type": "number", "enum": [1, 100]},
                    "label": {"type": "string"},
                },
                "required": ["numerator", "denominator", "scale", "label"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_change",
            "strict": True,
            "description": "Calculate an absolute and percentage change from cited start/end values.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_value": {"type": "number"},
                    "end_value": {"type": "number"},
                    "label": {"type": "string"},
                },
                "required": ["start_value", "end_value", "label"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_series",
            "strict": True,
            "description": (
                "Classify a time series deterministically and flag mixed annual, half-year, "
                "and quarterly cumulative reporting periods as not directly comparable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "periods": {"type": "array", "items": {"type": "integer"}},
                    "values": {"type": "array", "items": {"type": "number"}},
                    "label": {"type": "string"},
                },
                "required": ["periods", "values", "label"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_limitation",
            "strict": True,
            "description": (
                "Return a citable data/stage limitation. Use instead of repeated table queries "
                "when the question needs multiple tables, announcement body, control chain, "
                "consolidated statements, or unsupported data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limitation": {"type": "string", "enum": list(LIMITATIONS)},
                },
                "required": ["limitation"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_answer",
            "strict": True,
            "description": "Terminate and return the final answer. Evidence must cite query source strings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conclusion": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["conclusion", "evidence", "confidence"],
                "additionalProperties": False,
            },
        },
    },
]

SYSTEM_PROMPT = """你是 JRKJ 阶段2金融证据 Agent，负责多表、跨期和图谱辅助分析。
必须遵循：
1. 可以查询多张表。题目未明确给出日期时必须使用 date_mode=latest，并用 limit 指定最近记录数，严禁猜测日期；题目明确给出日期或范围时才使用 date_mode=range。
2. 跨表问题必须分别查询所需表，并按报告期对齐后再判断；不能用单表结果替代另一张表。
3. 共同股东问题调用 find_shareholder_connections；同名交叉只能作为待核实线索，不能直接认定同一主体或关联关系。
4. 需要公告正文时先调用 search_document_graph；当前没有正文覆盖时再调用 describe_limitation。股权图谱只能输出控制人候选路径，严禁把候选人直接认定为实际控制人；严禁把母公司报表称为合并报表。
5. 需要比率时调用 calculate_ratio；需要同比/差额时调用 calculate_change；需要趋势时调用 classify_series，不得心算。
6. 风险筛查使用 scorecard_screen 和 risk-policy-v1；模型分数只能是风险线索，不能生成“已确认财务造假”。
7. 数据不足时明确说明，不得补造事实；空值不能擅自视为0。
8. 可先召回同一数据版本的历史证据，但涉及最新数据或召回为空时必须查询原始表；工具返回的 source 必须原样引用。
9. 工具报错后不得重复相同调用；应根据错误信息换字段/条件，或调用 describe_limitation / finish_answer。
10. 必须调用 finish_answer终止。证据必须逐字包含工具返回的 _source，不得改写或自行构造；结论简洁，置信度表示数据支持程度。
11. 趋势比较必须先确认期间口径可比。年度累计、半年度累计和单季度不可当作同口径序列；口径不完整时明确限定结论。
"""


def query_table(
    table: str,
    windcode: str,
    date_mode: str,
    start_date: str,
    end_date: str,
    fields: list[str],
    limit: int,
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Query one indexed table and attach stable source identifiers."""
    if table not in TABLES:
        raise ValueError(f"Unsupported table: {table}")
    windcode = windcode.strip().upper()
    if not windcode:
        raise ValueError("windcode is required")
    limit = max(1, min(int(limit), 50))
    if date_mode not in {"latest", "range"}:
        raise ValueError("date_mode must be latest or range")
    time_column = TABLES[table]["time"]

    with sqlite3.connect(db_path) as connection:
        available = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        aliases = FIELD_ALIASES.get(table, {})
        requested = [aliases.get(field, field) for field in fields] or TABLES[table]["default_fields"]
        invalid = sorted(set(requested) - available)
        if invalid:
            raise ValueError(f"Unknown fields for {table}: {', '.join(invalid)}")

        start_value = normalize_date(start_date) if start_date else None
        end_value = normalize_date(end_date) if end_date else None
        if date_mode == "latest":
            start_value = end_value = None
        elif start_value is None:
            start_value = end_value
        elif end_value is None:
            end_value = start_value
        if date_mode == "range" and (start_value is None or end_value is None):
            raise ValueError("range mode requires start_date and end_date")
        if date_mode == "range" and start_value > end_value:
            raise ValueError("start_date must not be later than end_date")
        source_columns = ["s_info_windcode", time_column]
        selected = list(dict.fromkeys(source_columns + requested))
        quoted = ", ".join(f'"{column}"' for column in selected)
        order = f'"{time_column}" DESC'
        if table == "shareholders":
            order += ", s_holder_pct DESC"
        if date_mode == "latest":
            rows = connection.execute(
                f'SELECT {quoted} FROM "{table}" WHERE s_info_windcode = ? '
                f'ORDER BY {order} LIMIT ?',
                (windcode, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                f'SELECT {quoted} FROM "{table}" '
                f'WHERE s_info_windcode = ? AND "{time_column}" >= ? AND "{time_column}" <= ? '
                f'ORDER BY {order} LIMIT ?',
                (windcode, start_value, end_value, limit),
            ).fetchall()

    records = []
    evidence = []
    for row in rows:
        record = dict(zip(selected, row))
        if table.startswith("financial_"):
            statement_type = record.get("statement_type")
            if statement_type is None:
                statement_type = connection_statement_type(db_path, table, windcode, record[time_column])
            record["_statement_scope"] = (
                "母公司报表" if statement_type == 408006000 else "未知口径"
            )
        for field, value in list(record.items()):
            if isinstance(value, str) and len(value) > MAX_TOOL_TEXT_CHARS:
                record[field] = value[:MAX_TOOL_TEXT_CHARS]
                record[f"{field}_truncated"] = True
                record[f"{field}_original_chars"] = len(value)
        record["_source"] = (
            f"database/jrkj.sqlite3#{table}:"
            f"s_info_windcode={windcode},{time_column}={record[time_column]}"
        )
        records.append(record)
        evidence.append(
            Evidence(
                table=table,
                company=windcode,
                period_field=time_column,
                period=int(record[time_column]),
                values={field: record.get(field) for field in requested},
                source=record["_source"],
            ).to_dict()
        )
    return {
        "records": records,
        "evidence": evidence,
        "count": len(records),
        "query_range": {"mode": date_mode, "start": start_value, "end": end_value},
        "_source": (
            f"database/jrkj.sqlite3#{table}:s_info_windcode={windcode},"
            f"{time_column}="
            f"{'latest:' + str(limit) if date_mode == 'latest' else str(start_value) + '..' + str(end_value)}"
        ),
        "instruction": "Use these records and finish; do not call query_table again.",
    }


def connection_statement_type(
    db_path: Path, table: str, windcode: str, period: int
) -> Any:
    """Read the statement scope even when the model did not request the field."""
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        if "statement_type" not in columns:
            return None
        row = connection.execute(
            f'SELECT statement_type FROM "{table}" '
            'WHERE s_info_windcode=? AND report_period=? LIMIT 1',
            (windcode, period),
        ).fetchone()
    return row[0] if row else None


def calculate_ratio(numerator: float, denominator: float, scale: float, label: str) -> dict[str, Any]:
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    value = numerator / denominator * scale
    return {
        "label": label,
        "value": round(value, 6),
        "formula": f"{numerator} / {denominator} * {scale}",
    }


def describe_limitation(limitation: str) -> dict[str, str]:
    if limitation not in LIMITATIONS:
        raise ValueError("invalid limitation")
    return {
        "limitation": LIMITATIONS[limitation],
        "_source": f"README.md#data-boundary:{limitation}",
        "instruction": "Explain the limitation, use low confidence, and call finish_answer now.",
    }


def search_document_graph(
    windcode: str,
    query: str,
    kind: str,
    limit: int,
    documents_path: Path = PROJECT_ROOT / "data" / "enriched" / "announcement_documents.jsonl",
    graph_path: Path | None = None,
) -> dict[str, Any]:
    if kind not in {"", "announcement", "research"}:
        raise ValueError("kind must be empty, announcement, or research")
    if not documents_path.is_file():
        return {
            "records": [], "count": 0,
            "_source": "README.md#data-boundary:announcement_body",
            "limitation": "enriched document graph is not available for this dataset version",
        }
    graph_path = graph_path or Path(os.getenv("JRKJ_DOCUMENT_GRAPH_DB", str(PROJECT_ROOT / "data" / "enriched" / "document_graph.sqlite3")))
    graph = DocumentGraph(graph_path)
    try:
        if graph.document_count() == 0:
            graph.ingest_jsonl(documents_path)
        records = graph.search(windcode.upper(), query=query, kind=kind or None, limit=limit)
    finally:
        graph.close()
    evidence = []
    for record in records:
        source = f"document_graph#{record['document_id']}"
        evidence.append({
            "table": "document_graph", "company": windcode.upper(),
            "period_field": "published_at", "period": int(record["published_at"] or 0),
            "values": {
                "title": record.get("title"),
                "excerpt": record.get("excerpt", ""),
                "sha256": record.get("sha256"),
                "retrieved_at": record.get("retrieved_at"),
            },
            "source": source,
        })
    return {
        "records": records, "evidence": evidence, "count": len(records),
        "_source": "document_graph#enriched_documents",
        "warning": "Document text is source evidence; it does not by itself establish a legal finding.",
    }


def finish_answer(conclusion: str, evidence: list[str] | str, confidence: str) -> dict[str, Any]:
    if not conclusion.strip():
        raise ValueError("conclusion is required")
    if isinstance(evidence, str):
        try:
            decoded = json.loads(evidence)
        except json.JSONDecodeError as exc:
            raise ValueError("evidence string must contain a JSON array") from exc
        if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
            raise ValueError("evidence must be an array of strings")
        evidence = decoded
    if not evidence:
        raise ValueError("at least one evidence item is required")
    if not any(
        "database/jrkj.sqlite3#" in item
        or "neo4j#" in item
        or "document_graph#" in item
        or "README.md#data-boundary:" in item
        for item in evidence
    ):
        raise ValueError("evidence must include a database, graph, document, or data-boundary source")
    if confidence not in {"high", "medium", "low"}:
        raise ValueError("invalid confidence")
    return {"结论": conclusion, "证据": evidence, "置信度": confidence}


def graph_traversal(
    operation: str,
    windcode: str,
    target_windcode: str,
    end_date: str,
    max_hops: int,
    db_path: Path = DEFAULT_DB,
    backend_mode: str = "offline",
) -> dict[str, Any]:
    """Run a bounded, source-preserving shareholder graph operation."""
    if operation not in {"common_shareholders", "paths", "cycles", "controllers"}:
        raise ValueError("unsupported graph operation")
    windcode, target = windcode.strip().upper(), target_windcode.strip().upper()
    if operation in {"common_shareholders", "paths"} and not target:
        raise ValueError("target_windcode is required for this graph operation")
    if backend_mode not in {"neo4j", "offline", "sqlite"}:
        raise ValueError("backend_mode must be 'neo4j', 'sqlite', or 'offline'")
    backend, fallback_reason = "sqlite", ""
    if backend_mode == "neo4j":
        uri = os.getenv("NEO4J_URI")
        password = os.getenv("NEO4J_PASSWORD")
        if not uri or not password:
            raise RuntimeError("Neo4j graph mode requires NEO4J_URI and NEO4J_PASSWORD")
        neo = Neo4jOwnershipGraph(uri, os.getenv("NEO4J_USER", "neo4j"), password, os.getenv("NEO4J_DATABASE", "neo4j"))
        try:
            if not neo.verify_connectivity():
                raise RuntimeError("Neo4j connectivity check failed")
            if operation == "common_shareholders":
                records = neo.common_shareholders(windcode, target, period=end_date or None)
            elif operation == "paths":
                records = neo.paths(windcode, target, max_hops=max_hops, period=end_date or None)
            elif operation == "cycles":
                records = neo.circular_ownership(max_hops=max_hops)
            else:
                records = neo.ultimate_controllers(windcode, max_hops=max_hops, period=end_date or None)
            backend = "neo4j"
        finally:
            neo.close()
    else:
        graph = OwnershipGraph(db_path, end_date=end_date or None)
        records = (graph.common_shareholders(windcode, target) if operation == "common_shareholders" else
                   graph.paths(windcode, target, max_hops=max_hops) if operation == "paths" else
                   graph.circular_ownership(max_hops=max_hops) if operation == "cycles" else
                   graph.ultimate_controllers(windcode, max_hops=max_hops))
        fallback_reason = "explicit offline mode"
    evidence = []
    for record in records:
        if isinstance(record, list):
            edges = record
        elif operation == "common_shareholders" and backend == "neo4j":
            edges = [record.get("company_a", {}), record.get("company_b", {})]
            for edge in edges:
                edge["holder"] = record.get("holder")
        elif operation == "controllers":
            edges = record.get("path", [])
        elif backend == "neo4j":
            edges = record.get("edges", [])
        else:
            edges = [record["company_a"], record["company_b"]]
        for edge in edges:
            if not edge.get("source"):
                continue
            evidence.append({
                "table": "shareholders", "company": edge["company"],
                "period_field": "s_holder_enddate", "period": int(edge["period"]),
                "values": {"s_holder_name": edge.get("holder"), "s_holder_pct": edge.get("pct")},
                "source": ("neo4j#" if backend == "neo4j" else "database/jrkj.sqlite3#") + edge["source"],
            })
    return {
        "operation": operation, "records": records, "evidence": evidence,
        "count": len(records),
        "warning": "Top-shareholder name matches are investigative clues only, not proof of identity, control, or related-party relationships.",
        "backend": backend, "fallback_reason": fallback_reason,
        "_source": ("neo4j#ownership_graph:operation=" if backend == "neo4j" else "database/jrkj.sqlite3#ownership_graph:operation=") + operation,
    }


def scorecard_screen(model: str, values: dict[str, Any]) -> dict[str, Any]:
    if model == "beneish_m":
        return beneish_m_score(values)
    if model == "altman_z":
        return altman_z_score(values, private=bool(values.get("private", False)))
    if model == "piotroski_f":
        return piotroski_f_score(values)
    if model == "peer_z":
        if "value" not in values or "peers" not in values:
            raise ValueError("peer_z requires values.value and values.peers")
        return peer_zscore(values["value"], values["peers"])
    raise ValueError("unsupported scorecard model")


def agent_graph_traversal(**arguments: Any) -> dict[str, Any]:
    """Use the configured Agent execution profile without implicit fallback."""
    mode = os.getenv("JRKJ_GRAPH_MODE", GRAPH_MODE).strip().lower()
    return graph_traversal(**arguments, backend_mode=mode)


TOOL_HANDLERS = {
    "query_table": query_table,
    "search_document_graph": search_document_graph,
    "find_shareholder_connections": lambda windcode, end_date, top_n, limit: {
        "records": query_shareholder_connections(
            windcode, end_date=end_date or None, top_n=top_n, limit=limit
        ),
        "_source": f"database/jrkj.sqlite3#shareholder_graph:anchor={windcode.upper()}",
        "warning": "Exact-name matches are clues only and require identity verification."
    },
    "graph_traversal": agent_graph_traversal,
    "financial_risk_signals": financial_risk_signals,
    "financial_risk_signals_from_records": financial_risk_signals_from_records,
    "scorecard_screen": scorecard_screen,
    "classify_risk": classify_risk,
    "calculate_ratio": calculate_ratio,
    "calculate_change": calculate_change,
    "classify_series": classify_series,
    "describe_limitation": describe_limitation,
    "finish_answer": finish_answer,
}


def call_deepseek(
    messages: list[dict[str, Any]], api_key: str
) -> tuple[dict[str, Any], dict[str, int]]:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "thinking": {"type": "enabled"},
        "reasoning_effort": REASONING_EFFORT,
        "max_tokens": 2400,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek connection error: {exc.reason}") from exc
    return body["choices"][0]["message"], body.get("usage", {})


def run_agent(
    question: str,
    api_key: str | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    key = api_key or LLM_API_KEY
    if not key:
        raise RuntimeError("Set LLM_API_KEY in .env or in the environment.")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    data_calls = 0
    memory = TaskMemory()
    observed_sources: set[str] = set()
    persistent_memory = PersistentEvidenceMemory()
    context = ContextBuilder(persistent_memory).build(question, token_budget=3000)
    if context.get("context_text"):
        messages.insert(
            1,
            {
                "role": "system",
                "content": (
                    "相关长期证据上下文（仅作候选事实，必须保留来源；缺失时查询原表）：\n"
                    + context["context_text"]
                ),
            },
        )
    for _ in range(MAX_STEPS):
        response = call_deepseek(messages, key)
        if isinstance(response, tuple):
            message, usage = response
        else:  # Keep injected test clients simple.
            message, usage = response, {}
        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if trace is not None:
            trace.append(
                {
                    "event": "model_response",
                    "content": message.get("content"),
                    "reasoning_content": message.get("reasoning_content"),
                    "tool_calls": tool_calls,
                    "usage": usage,
                }
            )
        if not tool_calls:
            messages.append(
                {"role": "user", "content": "请按协议调用工具，并最终调用 finish_answer。"}
            )
            continue

        for tool_call in tool_calls:
            try:
                name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])
                if name not in TOOL_HANDLERS and name != "recall_evidence_memory":
                    raise ValueError(f"Unknown tool: {name}")
                if name == "recall_evidence_memory":
                    result = {
                        "records": persistent_memory.recall(
                            arguments["windcode"], arguments["table"] or None, arguments["limit"]
                        ),
                        "_source": "database/jrkj_memory.sqlite3#evidence_memory",
                        "instruction": "Use only exact records and preserve each nested source.",
                    }
                elif name in {"query_table", "find_shareholder_connections", "graph_traversal", "search_document_graph"}:
                    signature = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
                    if signature in memory.query_signatures:
                        raise ValueError(
                            "identical query_table call already used; do not repeat it."
                        )
                    if data_calls >= MAX_DATA_CALLS:
                        raise ValueError(
                            f"maximum of {MAX_DATA_CALLS} data queries reached; finish with "
                            "the collected evidence."
                        )
                    result: Any = TOOL_HANDLERS[name](**arguments)
                    data_calls += 1
                    memory.remember_query(signature, result)
                    if name == "query_table":
                        persistent_memory.remember_query(result)
                elif name == "describe_limitation":
                    result = TOOL_HANDLERS[name](**arguments)
                elif name == "finish_answer":
                    result = finish_answer(**arguments)
                    verification = verify_citations(result, observed_sources)
                    repair = repair_artifact(result, sorted(observed_sources))
                    if repair["repairable"] and not verification["valid"]:
                        result = repair["answer"]
                        verification = verify_citations(result, observed_sources)
                    if not verification["valid"]:
                        raise ValueError(
                            "finish_answer includes unsupported citations: "
                            + ", ".join(verification["unsupported_citations"])
                        )
                    if trace is not None:
                        trace.append({"event": "memory_snapshot", "result": memory.snapshot()})
                        trace.append({"event": "evidence_verification", "result": verification})
                        self_eval = evaluate_artifact(result, sorted(observed_sources), [])
                        self_eval["repair"] = repair
                        trace.append({"event": "self_evaluation", "result": self_eval})
                    return result
                else:
                    result = TOOL_HANDLERS[name](**arguments)
                    if name in {"calculate_ratio", "calculate_change", "classify_series"}:
                        memory.remember_calculation(name, result)
            except (KeyError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                result = {"error": str(exc)}
                if trace is not None:
                    failed_tool = tool_call.get("function", {}).get("name")
                    trace.append({"event": "error", "tool": failed_tool, "message": str(exc)})
                    if failed_tool != "finish_answer":
                        trace.append({"event": "retry", "tool": failed_tool, "reason": "tool_error"})
            if isinstance(result, dict):
                if result.get("_source"):
                    observed_sources.add(result["_source"])
                for item in result.get("evidence", []):
                    if isinstance(item, dict) and item.get("source"):
                        observed_sources.add(item["source"])
            if trace is not None:
                trace.append(
                    {
                        "event": "tool_result",
                        "tool": tool_call.get("function", {}).get("name"),
                        "result": result,
                    }
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
    raise RuntimeError("Agent did not call finish_answer within the step limit.")


def run_investigation(
    question: str,
    api_key: str | None = None,
) -> InvestigationRun:
    """Run the legacy Agent API while returning a serializable audit artifact."""
    trace: list[dict[str, Any]] = []
    answer = run_agent(question, api_key=api_key, trace=trace)
    return InvestigationRun.from_trace(question, trace, answer)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", help="single-hop financial question")
    args = parser.parse_args()
    question = args.question or input("Question: ").strip()
    print(json.dumps(run_agent(question), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
