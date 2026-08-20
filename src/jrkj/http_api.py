"""Standard-library HTTP adapter for the analyze service boundary."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .analyze import analyze_question
from .investigation_run import InvestigationRun
from .observability import RunStore


def make_handler(runner: Callable[..., InvestigationRun], static_dir: str | Path | None = None, run_store: RunStore | None = None):
    root = Path(static_dir).resolve() if static_dir else None

    class AnalyzeHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send(200, {"ok": True, "service": "jrkj"})
            elif run_store is not None and self.path == "/api/runs":
                self._send(200, {"ok": True, "runs": run_store.list()})
            elif run_store is not None and self.path.startswith("/api/runs/"):
                run_id = self.path.rsplit("/", 1)[-1]
                run = run_store.get(run_id)
                self._send(200 if run else 404, {"ok": True, "run": run} if run else {"ok": False, "error": {"code": "run_not_found", "message": run_id}})
            elif root is not None:
                self._serve_static()
            else:
                self._send(404, {"ok": False, "error": {"code": "not_found", "message": "route not found"}})

        def _serve_static(self) -> None:
            relative = self.path.split("?", 1)[0].lstrip("/") or "index.html"
            candidate = (root / relative).resolve()
            if root not in candidate.parents and candidate != root:
                self._send(404, {"ok": False, "error": {"code": "not_found", "message": "file not found"}})
                return
            if not candidate.is_file():
                self._send(404, {"ok": False, "error": {"code": "not_found", "message": "file not found"}})
                return
            content_types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
            body = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_types.get(candidate.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/api/analyze":
                self._send(404, {"ok": False, "error": {"code": "not_found", "message": "route not found"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object")
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                self._send(400, {"ok": False, "error": {"code": "invalid_json", "message": str(exc)}})
                return
            result = analyze_question(payload.get("question", ""), runner)
            if result.get("ok") and run_store is not None:
                run_store.save(result["run"])
            self._send(200 if result["ok"] else 400, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return AnalyzeHandler


def create_server(host: str, port: int, runner: Callable[..., InvestigationRun], static_dir: str | Path | None = None, run_store: RunStore | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(runner, static_dir, run_store))
