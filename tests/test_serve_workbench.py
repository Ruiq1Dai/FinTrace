from pathlib import Path


def test_workbench_script_has_explicit_server_entrypoint():
    script = (Path(__file__).parents[1] / "scripts" / "serve_workbench.py").read_text()
    assert "create_server" in script
    assert "frontend" in script
    assert "serve_forever" in script
