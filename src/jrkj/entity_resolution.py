"""Explicit, source-backed entity resolution for ownership graph edges."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_resolutions(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = Path(path)
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("entity resolution rows must be JSON objects")
        for field in ("holder_name", "security_code", "verification_source"):
            if not str(row.get(field, "")).strip():
                raise ValueError(f"entity resolution requires {field}")
        if row.get("verification_status") != "verified_external_source":
            raise ValueError("entity resolution status must be verified_external_source")
        rows.append(row)
    return rows


def apply_resolutions(entity_master_path: str | Path, resolution_path: str | Path, output_path: str | Path) -> int:
    """Copy the entity master and apply only explicitly sourced mappings."""
    resolutions = load_resolutions(resolution_path)
    by_name = {(str(row["holder_name"]).strip(), str(row["security_code"]).upper()): row for row in resolutions}
    output: list[dict[str, Any]] = []
    for line in Path(entity_master_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        key = (str(record.get("canonical_name", "")).strip(), str((record.get("company_scope") or [""])[0]).upper())
        resolution = by_name.get(key)
        if resolution and record.get("entity_type") == "holder":
            record = dict(record)
            record.update({
                "verification_status": "verified_external_source",
                "resolved_entity_id": resolution.get("entity_id", f"security:{str(resolution['security_code']).upper()}"),
                "resolved_security_code": str(resolution["security_code"]).upper(),
                "verification_source": resolution["verification_source"],
                "limitations": [],
            })
        output.append(record)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    return sum(record.get("verification_status") == "verified_external_source" for record in output)
