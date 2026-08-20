from scripts.smoke_test import run_smoke


def test_smoke_is_deterministic_without_external_graph():
    result = run_smoke(skip_neo4j=True)
    assert result["ok"] is True
    assert {item["name"] for item in result["checks"]} == {
        "data_contract", "document_graph", "deterministic_scorecard", "risk_policy", "neo4j"
    }
