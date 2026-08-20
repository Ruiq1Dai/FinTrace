import json

from jrkj.investigation_run import InvestigationRun


def test_investigation_run_collects_trace_artifacts():
    trace = [
        {"event": "model_response", "tool_calls": [{"id": "1", "function": {"name": "query_table"}}]},
        {"event": "tool_result", "tool": "query_table", "result": {
            "_source": "db#income", "evidence": [{"source": "db#income:period=2024"}],
        }},
        {"event": "tool_result", "tool": "calculate_change", "result": {"formula": "x-y", "value": 1}},
        {"event": "evidence_verification", "result": {"valid": True}},
    ]
    artifact = InvestigationRun.from_trace("test", trace, {"结论": "ok"}, run_id="run-1", started_at=1)
    assert artifact.run_id == "run-1"
    assert len(artifact.tool_calls) == 1
    assert artifact.evidence_sources == ["db#income", "db#income:period=2024"]
    assert artifact.verification["valid"] is True
    assert artifact.token_usage["total_tokens"] == 0
    assert artifact.elapsed_ms is not None
    assert json.loads(artifact.to_json())["question"] == "test"
