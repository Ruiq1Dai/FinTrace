import json
from pathlib import Path

from scripts.check_data import check_manifest


def test_data_manifest_is_explicit_and_complete_for_minimum_scope():
    path = Path(__file__).parents[1] / "data" / "manifest.json"
    result = check_manifest(path)
    assert result["policy_version"] == "risk-policy-v1"
    assert result["minimum_cases"] == ["600238.SH", "601033.SH", "300838.SZ"]
    assert {item["name"] for item in result["assets"]} == {
        "announcement_body", "consolidated_statements", "entity_master"
    }
    assert result["complete"] is True
    assert all(item["present"] for item in result["assets"])
