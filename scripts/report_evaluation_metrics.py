#!/usr/bin/env python3
"""Summarize InvestigationRun JSON artifacts."""

import argparse
import json
from pathlib import Path

from jrkj.evaluation_metrics import load_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(load_metrics(args.artifacts_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
