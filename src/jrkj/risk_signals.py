"""Explainable, deterministic financial anomaly signals.

Signals are leads for investigation, not fraud determinations. Thresholds are
optional and never imply a legal or audit conclusion.
"""

from __future__ import annotations

from typing import Any

from .calculations import period_kind
from .risk_thresholds import POLICY_VERSION, get_threshold


def _growth(start: float, end: float) -> float | None:
    if start == 0:
        return None
    return (end - start) / abs(start) * 100


def financial_risk_signals(
    periods: list[int],
    revenue: list[float | None],
    operating_cash_flow: list[float | None],
    receivables: list[float | None] | None = None,
    inventory: list[float | None] | None = None,
) -> dict[str, Any]:
    """Compare aligned periods and return auditable anomaly leads."""
    if len(periods) < 2 or len(periods) != len(revenue) or len(revenue) != len(operating_cash_flow):
        raise ValueError("periods, revenue and operating_cash_flow need equal length >= 2")
    if receivables is not None and len(receivables) != len(periods):
        raise ValueError("receivables must align with periods")
    if inventory is not None and len(inventory) != len(periods):
        raise ValueError("inventory must align with periods")
    rows = sorted(zip((int(p) for p in periods), revenue, operating_cash_flow,
                      receivables or [None] * len(periods), inventory or [None] * len(periods)))
    signals = []
    for previous, current in zip(rows, rows[1:]):
        period_a, rev_a, cash_a, recv_a, inv_a = previous
        period_b, rev_b, cash_b, recv_b, inv_b = current
        if None not in (rev_a, rev_b, cash_a, cash_b):
            rev_change = _growth(float(rev_a), float(rev_b))
            cash_change = _growth(float(cash_a), float(cash_b))
            divergent = (rev_change is not None and cash_change is not None and
                          ((rev_change > 0 and cash_change < 0) or
                           (rev_change < 0 and cash_change > 0)))
            signals.append({"type": "revenue_cashflow_divergence", "period_start": period_a,
                            "period_end": period_b, "signal": divergent,
                            "revenue_change_pct": rev_change, "cashflow_change_pct": cash_change,
                            "formula": "compare YoY directions of revenue and operating cash flow",
                            "limitation": "Directional divergence is an investigation lead, not proof of manipulation."})
        for kind, start, end in (("receivables", recv_a, recv_b), ("inventory", inv_a, inv_b)):
            if None not in (rev_a, rev_b, start, end):
                rev_change = _growth(float(rev_a), float(rev_b))
                item_change = _growth(float(start), float(end))
                excess = (item_change - rev_change) if rev_change is not None and item_change is not None else None
                threshold = get_threshold("signal_growth_excess_pct")
                faster = excess is not None and excess >= threshold
                signals.append({"type": f"{kind}_growth_exceeds_revenue", "period_start": period_a,
                                "period_end": period_b, "signal": faster,
                                "revenue_change_pct": rev_change, f"{kind}_change_pct": item_change,
                                "excess_pct": excess, "threshold_pct": threshold,
                                "policy_version": POLICY_VERSION,
                                "formula": f"{kind}_growth_pct > revenue_growth_pct",
                                "limitation": "Growth comparison is a screening signal and requires business-context review."})
    return {"signals": signals, "periods": [row[0] for row in rows], "signal_count": sum(item["signal"] for item in signals)}


def financial_risk_signals_from_records(
    income_records: list[dict[str, Any]],
    cashflow_records: list[dict[str, Any]],
    balance_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Align query results by report period and attach source evidence to signals."""
    def indexed(records: list[dict[str, Any]], field: str) -> dict[int, dict[str, Any]]:
        return {int(row["report_period"]): row for row in records
                if row.get("report_period") is not None and row.get(field) is not None}

    income = indexed(income_records, "oper_rev")
    cashflow = indexed(cashflow_records, "net_cash_flows_oper_act")
    balance = balance_records or []
    receivables = indexed(balance, "acct_rcv")
    inventory = indexed(balance, "inventories")
    periods = sorted(set(income) & set(cashflow))
    if len(periods) < 2:
        raise ValueError("at least two aligned income and cashflow periods are required")
    kinds = {period_kind(period) for period in periods}
    if len(kinds) != 1:
        return {"signals": [], "periods": periods, "signal_count": 0,
                "comparable": False,
                "warning": "Mixed cumulative reporting periods are not directly comparable.",
                "evidence": []}
    result = financial_risk_signals(
        periods,
        [income[p].get("oper_rev") for p in periods],
        [cashflow[p].get("net_cash_flows_oper_act") for p in periods],
        [receivables.get(p, {}).get("acct_rcv") for p in periods] if receivables else None,
        [inventory.get(p, {}).get("inventories") for p in periods] if inventory else None,
    )
    for signal in result["signals"]:
        source_rows = []
        for period in (signal["period_start"], signal["period_end"]):
            source_rows.extend(row.get("_source") for row in
                               (income.get(period), cashflow.get(period),
                                receivables.get(period), inventory.get(period)) if row and row.get("_source"))
        signal["evidence_sources"] = sorted(set(source_rows))
    result["comparable"] = True
    result["evidence"] = sorted({source for signal in result["signals"] for source in signal["evidence_sources"]})
    return result
