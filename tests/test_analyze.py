from jrkj.analyze import analyze_question
from jrkj.investigation_run import InvestigationRun


def runner(question, **kwargs):
    return InvestigationRun("run-test", question, 1.0, {"结论": "ok"})


def test_analyze_returns_stable_success_envelope():
    result = analyze_question("  test  ", runner)
    assert result["ok"] is True
    assert result["run"]["question"] == "test"
    assert result["run"]["run_id"] == "run-test"


def test_analyze_rejects_blank_question_without_runner_call():
    result = analyze_question(" ", runner)
    assert result == {"ok": False, "error": {"code": "invalid_question", "message": "question is required"}}


def test_analyze_converts_runner_failure_to_json_error():
    def failing(question, **kwargs):
        raise RuntimeError("missing API key")
    result = analyze_question("test", failing)
    assert result["ok"] is False
    assert result["error"]["code"] == "investigation_failed"
