import json
from pathlib import Path

import pytest

from jrkj.entity_resolution import apply_resolutions, load_resolutions


def test_resolution_requires_explicit_source(tmp_path: Path):
    path = tmp_path / "resolution.jsonl"
    path.write_text(json.dumps({"holder_name": "H", "security_code": "A", "verification_status": "unresolved_name_match"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="verification_source"):
        load_resolutions(path)


def test_resolution_updates_only_matching_holder(tmp_path: Path):
    master = tmp_path / "master.jsonl"
    master.write_text("\n".join([
        json.dumps({"entity_type": "holder", "canonical_name": "H", "company_scope": ["A"], "verification_status": "unresolved_name_match"}),
        json.dumps({"entity_type": "company", "security_code": "A", "verification_status": "verified_security_code"}),
    ]) + "\n", encoding="utf-8")
    resolution = tmp_path / "resolution.jsonl"
    resolution.write_text(json.dumps({"holder_name": "H", "security_code": "A", "entity_id": "security:A", "verification_status": "verified_external_source", "verification_source": "registry#A"}) + "\n", encoding="utf-8")
    output = tmp_path / "out.jsonl"
    assert apply_resolutions(master, resolution, output) == 1
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["verification_status"] == "verified_external_source"
    assert rows[0]["verification_source"] == "registry#A"
