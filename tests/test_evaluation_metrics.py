from jrkj.evaluation_metrics import artifact_metrics, load_metrics


def test_artifact_metrics_calculates_success_and_coverage():
    metrics = artifact_metrics({
        "tool_calls": [{"id": "1"}],
        "tool_results": [{"result": {"evidence": [{"source": "s"}]}}, {"result": {"error": "bad"}}],
        "evidence_sources": ["s"],
        "answer": {"证据": ["s"]},
        "verification": {"unsupported_citations": []},
        "elapsed_ms": 10,
        "token_usage": {"total_tokens": 20},
    })
    assert metrics["tool_success_rate"] == 0.5
    assert metrics["evidence_coverage"] == 1.0
    assert metrics["elapsed_ms"] == 10
    assert metrics["total_tokens"] == 20


def test_load_metrics_aggregates_json(tmpdir):
    directory = tmpdir.mkdir("artifacts")
    directory.join("Q1.json").write('{"tool_calls": [], "tool_results": [], "answer": {"证据": []}}')
    result = load_metrics(directory)
    assert result["count"] == 1
    assert result["valid_count"] == 1
