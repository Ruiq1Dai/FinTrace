#!/usr/bin/env python3
"""Export the auditable financial slice for the selected demo cases."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CASES = ("600238.SH", "601033.SH", "300838.SZ")

FIELDS = {
    "financial_income": {
        "revenue": "tot_oper_rev",
        "net_profit": "net_profit_incl_min_int_inc",
    },
    "financial_balance": {
        "accounts_receivable": "acct_rcv",
        "inventories": "inventories",
        "total_assets": "tot_assets",
        "total_liabilities": "tot_liab",
        "total_equity": "tot_shrhldr_eqy_incl_min_int",
    },
    "financial_cashflow": {
        "operating_cash_flow": "net_cash_flows_oper_act",
        "cash_end": "cash_cash_equ_end_period",
    },
}


def build_consolidated_statements(sqlite_path: Path, cases: tuple[str, ...] = CASES) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    with sqlite3.connect(sqlite_path) as connection:
        for table, metrics in FIELDS.items():
            columns = ", ".join(["s_info_windcode", "report_period", "statement_type", "crncy_code", "object_id"] + list(metrics.values()))
            query = f"SELECT {columns} FROM {table} WHERE upper(s_info_windcode) IN ({','.join('?' for _ in cases)})"
            for row in connection.execute(query, tuple(code.upper() for code in cases)):
                code, period, statement_type, currency, object_id, *values = row
                for metric, field, value in zip(metrics, metrics.values(), values):
                    rows.append({
                        "security_code": str(code).upper(),
                        "report_period": int(period),
                        "statement_type": int(statement_type) if statement_type is not None else None,
                        "currency": currency,
                        "metric": metric,
                        "value": value,
                        "source_table": table,
                        "source_field": field,
                        "source_id": object_id,
                        "source": f"database/jrkj.sqlite3#{table}:{object_id}",
                    })
    return pd.DataFrame(rows).sort_values(["security_code", "report_period", "metric"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=ROOT / "database" / "jrkj.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "enriched" / "consolidated_statements.parquet")
    args = parser.parse_args()
    frame = build_consolidated_statements(args.sqlite)
    if frame.empty:
        raise SystemExit("no financial records found for the minimum cases")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    print({"output": str(args.output), "rows": len(frame), "cases": sorted(frame.security_code.unique().tolist()), "periods": sorted(frame.report_period.unique().tolist())})


if __name__ == "__main__":
    main()
