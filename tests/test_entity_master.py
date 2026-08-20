import json
import sqlite3
from pathlib import Path

from scripts.build_entity_master import build_entity_master
from scripts.check_data import check_manifest


def test_entity_master_marks_security_codes_verified_and_holders_unresolved(tmp_path: Path):
    db = tmp_path / "jrkj.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript("""
        CREATE TABLE research_reports (s_info_windcode TEXT, sec_name TEXT, publish_date INTEGER);
        CREATE TABLE shareholders (s_info_windcode TEXT, s_holder_enddate INTEGER, s_holder_name TEXT, s_holder_pct REAL, s_holder_sequence INTEGER);
        INSERT INTO research_reports VALUES ('601033.SH', '永兴股份', 20260101);
        INSERT INTO shareholders VALUES ('601033.SH', 20260331, '某股东', 10, 1);
        """)
    records = build_entity_master(db, cases=("601033.SH",), holder_limit=10)
    company = records[0]
    holder = records[1]
    assert company["verification_status"] == "verified_security_code"
    assert company["canonical_name"] == "永兴股份"
    assert holder["verification_status"] == "unresolved_name_match"
    assert holder["limitations"]


def test_data_checker_requires_verified_minimum_cases():
    path = Path(__file__).parents[1] / "data" / "manifest.json"
    result = check_manifest(path)
    assert "entity_master_verified_cases" in result
    assert result["entity_master_cases_complete"] is True
    assert result["complete"] is True
