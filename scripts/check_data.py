#!/usr/bin/env python3
"""Check the auditable data contract without inventing data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "manifest.json"


def check_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = []
    for item in payload.get("required_assets", []):
        asset_path = ROOT / item["path"]
        assets.append({
            "name": item["name"],
            "path": item["path"],
            "present": asset_path.is_file() and asset_path.stat().st_size > 0,
            "description": item.get("description", ""),
        })
    entity_asset = next((item for item in assets if item["name"] == "entity_master"), None)
    verified_cases: list[str] = []
    if entity_asset and entity_asset["present"]:
        entity_path = ROOT / entity_asset["path"]
        for line in entity_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("entity_type") == "company" and record.get("verification_status") == "verified_security_code":
                verified_cases.append(str(record.get("security_code", "")).upper())
    required_cases = [str(case).upper() for case in payload.get("minimum_cases", [])]
    return {
        "policy_version": payload.get("policy_version"),
        "minimum_cases": payload.get("minimum_cases", []),
        "assets": assets,
        "entity_master_verified_cases": sorted(set(verified_cases).intersection(required_cases)),
        "entity_master_cases_complete": set(required_cases).issubset(set(verified_cases)),
        "complete": all(item["present"] for item in assets) and set(required_cases).issubset(set(verified_cases)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--strict", action="store_true", help="exit non-zero when an asset is missing")
    args = parser.parse_args()
    result = check_manifest(args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.strict and not result["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
