from jrkj.evidence_verifier import verify_citations


def test_accepts_observed_source_prefix():
    result = verify_citations(
        {"证据": ["database/jrkj.sqlite3#financial_income:s_info_windcode=A"]},
        ["database/jrkj.sqlite3#financial_income:s_info_windcode=A,report_period=20241231"],
    )
    assert result["valid"]


def test_rejects_unobserved_source():
    result = verify_citations(
        {"证据": ["database/jrkj.sqlite3#financial_income:s_info_windcode=B"]},
        ["database/jrkj.sqlite3#financial_income:s_info_windcode=A,report_period=20241231"],
    )
    assert not result["valid"]
