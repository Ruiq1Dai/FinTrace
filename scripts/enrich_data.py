#!/usr/bin/env python3
"""Download a small, provenance-preserving announcement-text sample.

This deliberately handles only public PDF links already present in the local
announcement index. It never invents document text and leaves the source URL,
hash, retrieval time, and page boundaries in the JSONL output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "database" / "jrkj.sqlite3"
DEFAULT_OUTPUT = ROOT / "data" / "enriched" / "announcement_documents.jsonl"


def extract_pdf_text(content: bytes) -> tuple[str, list[str]]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as file:
        file.write(content)
        file.flush()
        completed = subprocess.run(
            ["pdftotext", "-layout", file.name, "-"],
            check=True,
            capture_output=True,
        )
    text = completed.stdout.decode("utf-8", errors="replace").strip()
    pages = [page.strip() for page in text.split("\f") if page.strip()]
    return text, pages


def download_announcements(
    db_path: Path,
    output_path: Path,
    company: str,
    limit: int,
    timeout: int = 30,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT object_id, s_info_windcode, ann_dt, n_info_title, n_info_annlink "
            "FROM announcements WHERE s_info_windcode=? AND n_info_annlink IS NOT NULL "
            "ORDER BY ann_dt DESC LIMIT ?",
            (company.upper(), max(1, min(int(limit), 20))),
        ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for row in rows:
        url = str(row["n_info_annlink"])
        request = urllib.request.Request(url, headers={"User-Agent": "JRKJ/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read()
        text, pages = extract_pdf_text(content)
        records.append({
            "document_id": str(row["object_id"]),
            "company": str(row["s_info_windcode"]).upper(),
            "published_at": int(row["ann_dt"]),
            "title": row["n_info_title"],
            "source": url,
            "sha256": hashlib.sha256(content).hexdigest(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "text": text,
            "pages": pages,
        })
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"company": company.upper(), "count": len(records), "output": str(output_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--company", default="600238.SH")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(download_announcements(args.db, args.output, args.company, args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
