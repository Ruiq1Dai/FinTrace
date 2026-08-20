#!/usr/bin/env python3
"""Add beginner-friendly, row-level source locations to evaluation CSV files."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "database" / "jrkj.sqlite3"

TABLES = {
    # Names are deliberately descriptive: the audience should not need finance
    # knowledge to understand what a source contains.
    "financial_income": ("公司赚了多少钱（收入和利润表）", "data/4/ashareincome_202605261519.csv", "report_period"),
    "financial_balance": ("公司现在有什么、欠什么（资产负债表）", "data/4/asharebalancesheet_202605261517.csv", "report_period"),
    "financial_cashflow": ("公司现金实际进出多少（现金流量表）", "data/4/asharecashflow_202605261518.csv", "report_period"),
    "shareholders": ("谁持有这家公司（前十大股东快照）", "data/2/上市公司前十大股东.xlsx（工作表：十大股东；原始表名：clean.xlsx）", "s_holder_enddate"),
    "announcements": ("公司发布过什么风险公告（公告目录）", "data/3/公司风险公告目录.xlsx（原始表名：clean.xlsx）", "ann_dt"),
    "research_reports": ("证券机构如何分析这家公司（研报摘要）", "data/5/rr_main_202605281537.csv", "publish_date"),
}

FIELDS = {
    "oper_rev": "营业收入（公司卖产品或服务取得的收入）",
    "net_profit_excl_min_int_inc": "净利润（收入减去各类成本费用后的结果）",
    "oper_profit": "营业利润（公司经营活动的盈亏）",
    "plus_net_invest_inc": "投资收益（投资带来的盈利或亏损）",
    "plus_net_gain_chg_fv": "公允价值变动收益（资产估值变化形成的账面盈亏）",
    "acct_rcv": "应收账款（已经确认销售但还没收回的钱）",
    "inventories": "存货（尚未卖出的商品或原材料）",
    "st_borrow": "短期借款（一年内通常需要偿还的借款）",
    "monetary_cap": "货币资金（现金和银行存款等）",
    "net_cash_flows_oper_act": "经营活动现金流量净额（主营经营实际流入减流出的现金）",
    "s_holder_name": "股东名称",
    "s_holder_pct": "持股比例",
    "n_info_title": "公告标题",
    "n_info_fcode": "公告分类",
    "n_info_annlink": "公告 PDF 链接",
    "title": "研报标题",
    "abstract": "研报摘要（证券机构的文字分析）",
    "statement_type": "报表口径代码",
}

REFERENCE_SPECS: dict[str, list[tuple[str, str, tuple[Any, ...], list[str]]]] = {
    "Q1": [("financial_income", "s_info_windcode=? AND report_period=?", ("600238.SH", 20251231), ["oper_rev", "net_profit_excl_min_int_inc"])],
    "Q2": [("shareholders", "s_info_windcode=? AND s_holder_enddate=? AND s_holder_name=?", ("600238.SH", 20260331, "海口市国有资产经营有限公司"), ["s_holder_name", "s_holder_pct"])],
    "Q3": [("financial_cashflow", "s_info_windcode=? AND report_period=?", ("600238.SH", 20251231), ["net_cash_flows_oper_act"])],
    "Q4": [("financial_income", "s_info_windcode=? AND report_period IN (?,?)", ("600238.SH", 20241231, 20251231), ["oper_rev"])],
    "Q5": [("financial_income", "s_info_windcode=? AND report_period IN (?,?,?)", ("600238.SH", 20241231, 20250630, 20251231), ["net_profit_excl_min_int_inc"])],
    "Q6": [
        ("financial_income", "s_info_windcode=? AND report_period IN (?,?,?)", ("600238.SH", 20241231, 20250630, 20251231), ["net_profit_excl_min_int_inc"]),
        ("financial_cashflow", "s_info_windcode=? AND report_period IN (?,?,?)", ("600238.SH", 20241231, 20250630, 20251231), ["net_cash_flows_oper_act"]),
    ],
    "Q7": [
        ("financial_income", "s_info_windcode=? AND report_period IN (?,?)", ("600238.SH", 20241231, 20251231), ["oper_rev"]),
        ("financial_balance", "s_info_windcode=? AND report_period IN (?,?)", ("600238.SH", 20241231, 20251231), ["acct_rcv", "inventories"]),
    ],
    "Q8": [("financial_income", "s_info_windcode=? AND report_period=?", ("600238.SH", 20251231), ["net_profit_excl_min_int_inc", "plus_net_invest_inc", "plus_net_gain_chg_fv", "oper_profit"])],
    "Q9": [
        ("financial_balance", "s_info_windcode=? AND report_period IN (?,?)", ("600238.SH", 20241231, 20251231), ["st_borrow", "monetary_cap"]),
        ("financial_cashflow", "s_info_windcode=? AND report_period IN (?,?)", ("600238.SH", 20241231, 20251231), ["net_cash_flows_oper_act"]),
    ],
    "Q10": [
        ("financial_income", "s_info_windcode=? AND report_period IN (?,?,?)", ("600238.SH", 20241231, 20250630, 20251231), ["oper_rev", "net_profit_excl_min_int_inc"]),
        ("financial_balance", "s_info_windcode=? AND report_period IN (?,?,?)", ("600238.SH", 20241231, 20250630, 20251231), ["acct_rcv", "inventories", "monetary_cap"]),
        ("financial_cashflow", "s_info_windcode=? AND report_period IN (?,?,?)", ("600238.SH", 20241231, 20250630, 20251231), ["net_cash_flows_oper_act"]),
    ],
    "Q11": [
        ("shareholders", "s_holder_name=? AND ((s_info_windcode=? AND s_holder_enddate=?) OR (s_info_windcode=? AND s_holder_enddate=?) OR (s_info_windcode=? AND s_holder_enddate=?))", ("北京燕赵汇金国际投资有限责任公司", "600238.SH", 20260331, "000955.SZ", 20241231, "600365.SH", 20250630), ["s_holder_name", "s_holder_pct"]),
        ("shareholders", "s_holder_name=? AND ((s_info_windcode=? AND s_holder_enddate=?) OR (s_info_windcode=? AND s_holder_enddate=?) OR (s_info_windcode=? AND s_holder_enddate=?))", ("王松涛", "600238.SH", 20260331, "000955.SZ", 20251231, "300152.SZ", 20250930), ["s_holder_name", "s_holder_pct"]),
    ],
    "Q12": [("shareholders", "s_info_windcode=? AND s_holder_enddate IN (?,?)", ("600238.SH", 20250930, 20260331), ["s_holder_name", "s_holder_pct"])],
    "Q13": [("announcements", "s_info_windcode=? AND ann_dt>=?", ("600238.SH", 20230811), ["ann_dt", "n_info_title"])],
    "Q15": [
        ("research_reports", "s_info_windcode=? AND publish_date=? AND abstract LIKE ?", ("601033.SH", 20260329, "%8.61%"), ["title", "abstract"]),
        ("financial_income", "s_info_windcode=? AND report_period=?", ("601033.SH", 20251231), ["statement_type", "net_profit_excl_min_int_inc"]),
    ],
    "Q16": [("research_reports", "s_info_windcode=? AND abstract LIKE ?", ("601033.SH", "%风险提示%"), ["publish_date", "title", "abstract"])],
    "Q17": [("announcements", "s_info_windcode=? AND ann_dt>=?", ("600238.SH", 20230811), ["n_info_title", "n_info_fcode", "n_info_annlink"])],
    "Q19": [("financial_income", "s_info_windcode=? AND report_period=?", ("600238.SH", 20251231), ["statement_type", "oper_rev"])],
}

SOURCE_RE = re.compile(r"#(?P<table>[a-z_]+):s_info_windcode=(?P<code>[0-9A-Z.]+),(?P<time>[a-z_]+)=(?P<value>\d{8})$")


def value_text(value: Any, field: str) -> str:
    if value is None:
        return "空白（不能当作 0）"
    if field in {"report_period", "ann_dt", "publish_date", "s_holder_enddate"}:
        text = str(value)
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 else text
    if isinstance(value, float):
        return f"{value:,.2f}"
    text = str(value).replace("\n", " ").strip()
    return text if len(text) <= 180 else text[:180] + "……"


def locate(connection: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...], fields: list[str]) -> list[str]:
    name, path, time_field = TABLES[table]
    selected = list(dict.fromkeys([time_field, "s_info_windcode", *fields]))
    sql = f'SELECT rowid AS _row, {", ".join(selected)} FROM "{table}" WHERE {where} ORDER BY {time_field}, rowid'
    rows = connection.execute(sql, params).fetchall()
    results = []
    for row in rows:
        # SQLite rowid 1 is the first data record; spreadsheet/CSV row 1 is the header.
        location = int(row["_row"]) + 1
        values = "；".join(f"{FIELDS.get(field, field)}={value_text(row[field], field)}" for field in fields)
        results.append(
            f"【{name}】（技术表名：{table}）\n"
            f"原始文件：{path}\n"
            f"定位：第 {location} 行（第 1 行是字段名，所以数据第 1 行对应文件第 2 行）；"
            f"筛选条件：股票代码={row['s_info_windcode']}，日期={value_text(row[time_field], time_field)}\n"
            f"该行实际值：{values}"
        )
    return results


def reference_sources(connection: sqlite3.Connection, question_id: str) -> str:
    if question_id == "Q14":
        count = connection.execute(
            "SELECT COUNT(*) FROM announcements WHERE s_info_windcode=? AND n_info_title LIKE ?",
            ("600238.SH", "%担保%"),
        ).fetchone()[0]
        return f"【公司发布过什么风险公告（公告目录）】（技术表名：announcements）\n原始文件：data/3/公司风险公告目录.xlsx（原始表名：clean.xlsx）\n筛选条件：股票代码=600238.SH，公告标题包含“担保”\n结果：匹配 {count} 行。没有匹配行只能说明当前目录未找到，不能证明公司一定没有担保。"
    if question_id == "Q18":
        return "【谁持有这家公司（前十大股东快照）】（技术表名：shareholders）\n原始文件：data/2/上市公司前十大股东.xlsx（工作表：十大股东；原始表名：clean.xlsx）\n这张表只有股东名称、持股数和持股比例等字段，没有“实际控制人”或“控制链”字段；本题应判断为数据不足，不需要金融推理。"
    lines: list[str] = []
    for spec in REFERENCE_SPECS.get(question_id, []):
        lines.extend(locate(connection, *spec))
    return "\n".join(lines)


def agent_sources(connection: sqlite3.Connection, raw: str) -> str:
    lines: list[str] = []
    seen: set[tuple[str, str, int]] = set()
    for source in raw.splitlines():
        match = SOURCE_RE.search(source.strip())
        if not match:
            continue
        table, code = match.group("table"), match.group("code")
        if table not in TABLES:
            continue
        time_field = TABLES[table][2]
        date = int(match.group("value"))
        key = (table, code, date)
        if key in seen:
            continue
        seen.add(key)
        default_fields = {
            "financial_income": ["oper_rev", "oper_profit", "net_profit_excl_min_int_inc"],
            "financial_balance": ["monetary_cap", "acct_rcv", "inventories", "st_borrow"],
            "financial_cashflow": ["net_cash_flows_oper_act"],
            "shareholders": ["s_holder_name", "s_holder_pct"],
            "announcements": ["n_info_title"],
            "research_reports": ["title", "abstract"],
        }[table]
        lines.extend(locate(connection, table, f"s_info_windcode=? AND {time_field}=?", (code, date), default_fields))
    if lines:
        return "\n".join(lines)
    if "README.md#data-boundary" in raw:
        return "Agent 没有查询原始数据行，只引用了项目的数据能力边界说明。请结合左侧“参考答案白话来源定位”判断它是否正确拒答。"
    return "Agent 没有留下可定位到原始表格行的查询证据。"


def enrich(input_path: Path, output_path: Path, db_path: Path) -> None:
    with input_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        original_fields = reader.fieldnames or []
    new_fields = []
    for field in original_fields:
        new_fields.append(field)
        if field == "参考数据来源":
            new_fields.append("参考答案白话来源定位")
        if field == "agent_数据来源引用":
            new_fields.append("agent_白话来源定位")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        for row in rows:
            row["参考答案白话来源定位"] = reference_sources(connection, row["question_id"])
            row["agent_白话来源定位"] = agent_sources(connection, row["agent_数据来源引用"])
    finally:
        connection.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=new_fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    for input_path in args.inputs:
        output = input_path.with_name(input_path.stem + "_beginner.csv")
        enrich(input_path, output, args.db)
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
