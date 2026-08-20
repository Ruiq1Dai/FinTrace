import pytest

from jrkj.risk_signals import financial_risk_signals


def test_directional_revenue_cashflow_divergence():
    result = financial_risk_signals([20231231, 20241231], [100, 120], [50, 40])
    signal = result["signals"][0]
    assert signal["signal"] is True
    assert signal["revenue_change_pct"] == 20
    assert signal["cashflow_change_pct"] == -20


def test_receivables_growth_signal_and_no_fraud_label():
    result = financial_risk_signals([20231231, 20241231], [100, 120], [50, 60], [10, 20])
    signal = next(item for item in result["signals"] if item["type"].startswith("receivables"))
    assert signal["signal"] is True
    assert "fraud" not in signal["type"]


def test_requires_aligned_periods():
    with pytest.raises(ValueError):
        financial_risk_signals([20231231], [100], [50])
