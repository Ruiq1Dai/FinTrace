from jrkj.advanced_scores import peer_zscore
from jrkj.risk_policy import classify_risk
from jrkj.risk_thresholds import POLICY_VERSION, policy_metadata


def test_risk_policy_separates_confirmed_fact_from_model_risk():
    result = classify_risk(
        ["revenue_cashflow", "receivables"],
        ["regulatory_decision"],
        data_sufficient=True,
        comparable_periods=2,
        official_finding=True,
    )
    assert result["risk_code"] == "confirmed_fact"
    assert result["policy_version"] == POLICY_VERSION


def test_risk_policy_requires_strong_external_evidence_for_high():
    result = classify_risk(
        ["revenue_cashflow", "receivables"],
        ["research_report"],
        data_sufficient=True,
        comparable_periods=2,
    )
    assert result["risk_code"] == "medium"
    assert classify_risk([], data_sufficient=False)["risk_code"] == "insufficient_data"


def test_policy_metadata_and_peer_screening_guardrail():
    assert policy_metadata()["policy_version"] == "risk-policy-v1"
    assert peer_zscore(20, list(range(10)))["screening_flag"] is True
    assert peer_zscore(4, [0, 1, 2])["screening_flag"] is False
