import json

from scripts.run_agent_evaluation import write_artifact


def test_evaluation_writes_investigation_artifact(tmpdir):
    path = write_artifact(
        tmpdir, "QX", "test question", [], {"结论": "ok", "证据": [], "置信度": "low"}
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "QX.json"
    assert payload["run_id"] == "QX"
    assert payload["question"] == "test question"
