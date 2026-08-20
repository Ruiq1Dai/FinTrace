import json
import threading
import urllib.request
from urllib.error import HTTPError

from jrkj.http_api import create_server
from jrkj.investigation_run import InvestigationRun
from jrkj.observability import RunStore
from pathlib import Path


def runner(question, **kwargs):
    return InvestigationRun("http-test", question, 1.0, {"结论": "ok"})


def test_http_health_and_analyze_routes():
    server = create_server("127.0.0.1", 0, runner, Path(__file__).parents[1] / "frontend")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%s" % server.server_address[1]
    try:
        with urllib.request.urlopen(base + "/health") as response:
            assert json.loads(response.read())["service"] == "jrkj"
        with urllib.request.urlopen(base + "/") as response:
            assert b"JRKJ" in response.read()
        with urllib.request.urlopen(base + "/app.js") as response:
            assert b"/api/analyze" in response.read()
        request = urllib.request.Request(
            base + "/api/analyze",
            data=json.dumps({"question": "hello"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            body = json.loads(response.read())
        assert body["ok"] is True
        assert body["run"]["question"] == "hello"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_persists_and_reads_run_store(tmp_path):
    store = RunStore(tmp_path / "runs.jsonl")
    server = create_server("127.0.0.1", 0, runner, run_store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%s" % server.server_address[1]
    try:
        request = urllib.request.Request(base + "/api/analyze", data=json.dumps({"question": "hello"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request) as response:
            assert json.loads(response.read())["ok"] is True
        with urllib.request.urlopen(base + "/api/runs/http-test") as response:
            assert json.loads(response.read())["run"]["run_id"] == "http-test"
        with urllib.request.urlopen(base + "/api/runs") as response:
            assert json.loads(response.read())["runs"][0]["run_id"] == "http-test"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_rejects_invalid_json():
    server = create_server("127.0.0.1", 0, runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:%s/api/analyze" % server.server_address[1]
    try:
        request = urllib.request.Request(url, data=b"not-json", method="POST")
        try:
            urllib.request.urlopen(request)
        except HTTPError as exc:
            assert exc.code == 400
            assert json.loads(exc.read())["error"]["code"] == "invalid_json"
        else:
            raise AssertionError("expected HTTP 400")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
