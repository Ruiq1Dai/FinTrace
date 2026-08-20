import sqlite3
from pathlib import Path

from scripts.build_consolidated_statements import build_consolidated_statements


def test_consolidated_export_keeps_source_table_and_field(tmp_path: Path):
    db = tmp_path / "jrkj.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript("""
        CREATE TABLE financial_income (s_info_windcode TEXT, report_period INTEGER, statement_type INTEGER, crncy_code TEXT, object_id TEXT, tot_oper_rev REAL, net_profit_incl_min_int_inc REAL);
        CREATE TABLE financial_balance (s_info_windcode TEXT, report_period INTEGER, statement_type INTEGER, crncy_code TEXT, object_id TEXT, acct_rcv REAL, inventories REAL, tot_assets REAL, tot_liab REAL, tot_shrhldr_eqy_incl_min_int REAL);
        CREATE TABLE financial_cashflow (s_info_windcode TEXT, report_period INTEGER, statement_type INTEGER, crncy_code TEXT, object_id TEXT, net_cash_flows_oper_act REAL, cash_cash_equ_end_period REAL);
        INSERT INTO financial_income VALUES ('600238.SH', 20241231, 408006000, 'CNY', 'i1', 100, 8);
        INSERT INTO financial_balance VALUES ('600238.SH', 20241231, 408006000, 'CNY', 'b1', 20, 5, 200, 100, 100);
        INSERT INTO financial_cashflow VALUES ('600238.SH', 20241231, 408006000, 'CNY', 'c1', 12, 30);
        """)
    frame = build_consolidated_statements(db, cases=("600238.SH",))
    assert set(frame["metric"]) == {"revenue", "net_profit", "accounts_receivable", "inventories", "total_assets", "total_liabilities", "total_equity", "operating_cash_flow", "cash_end"}
    assert frame.loc[frame["metric"] == "revenue", "source_field"].item() == "tot_oper_rev"
