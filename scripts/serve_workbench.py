#!/usr/bin/env python3
"""Serve the JRKJ frontend and analyze API from one origin."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent import run_investigation  # noqa: E402
from jrkj.http_api import create_server  # noqa: E402
from jrkj.observability import RunStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--static-dir", type=Path, default=PROJECT_ROOT / "frontend")
    parser.add_argument("--run-store", type=Path, default=PROJECT_ROOT / "logs" / "investigation_runs.jsonl")
    args = parser.parse_args()
    server = create_server(args.host, args.port, run_investigation, args.static_dir, RunStore(args.run_store))
    print(f"JRKJ workbench: http://{args.host}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
