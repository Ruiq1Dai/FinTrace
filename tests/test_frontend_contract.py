from pathlib import Path


def test_frontend_posts_to_analyze_and_has_demo_fallback():
    script = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "fetch('/api/analyze'" in script
    assert "当前显示演示数据" in script
    assert "JSON.stringify({question" in script
    assert "token_usage" in script
    assert "unsupported_citations" in script
    assert "tool_results" in script
    assert "escapeHtml" in script
