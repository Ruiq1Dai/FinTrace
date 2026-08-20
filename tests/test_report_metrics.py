from pathlib import Path


def test_metrics_report_script_exists():
    script = (Path(__file__).parents[1] / "scripts" / "report_evaluation_metrics.py").read_text()
    assert "load_metrics" in script
    assert "json.dumps" in script
