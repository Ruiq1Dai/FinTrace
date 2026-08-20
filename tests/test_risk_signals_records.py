import pytest

from jrkj.risk_signals import financial_risk_signals_from_records


def row(period, field, value, source):
    return {"report_period": period, field: value, "_source": source}


def test_record_wrapper_aligns_and_attaches_sources():
    result = financial_risk_signals_from_records(
        [row(20231231, "oper_rev", 100, "income-a"), row(20241231, "oper_rev", 120, "income-b")],
        [row(20231231, "net_cash_flows_oper_act", 50, "cash-a"), row(20241231, "net_cash_flows_oper_act", 40, "cash-b")],
    )
    assert result["comparable"] is True
    assert result["signals"][0]["signal"] is True
    assert set(result["signals"][0]["evidence_sources"]) == {"income-a", "income-b", "cash-a", "cash-b"}


def test_record_wrapper_rejects_mixed_period_kinds():
    result = financial_risk_signals_from_records(
        [row(20231231, "oper_rev", 100, "i1"), row(20240630, "oper_rev", 120, "i2")],
        [row(20231231, "net_cash_flows_oper_act", 50, "c1"), row(20240630, "net_cash_flows_oper_act", 40, "c2")],
    )
    assert result["comparable"] is False
    assert result["signals"] == []
