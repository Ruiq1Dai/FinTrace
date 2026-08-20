"""Small document/entity graph adapter for announcements and research evidence."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any


class DocumentGraph:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (document_id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT, published_at TEXT, source TEXT NOT NULL, text TEXT, sha256 TEXT, retrieved_at TEXT, metadata TEXT);
        CREATE TABLE IF NOT EXISTS document_entities (document_id TEXT NOT NULL, entity TEXT NOT NULL, entity_type TEXT, PRIMARY KEY(document_id, entity));
        CREATE INDEX IF NOT EXISTS idx_document_entity ON document_entities(entity);
        CREATE INDEX IF NOT EXISTS idx_document_published ON documents(published_at DESC);
        """)
        # Databases created by the earlier adapter predate these columns.
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(documents)")}
        for name, definition in (("sha256", "TEXT"), ("retrieved_at", "TEXT"), ("metadata", "TEXT")):
            if name not in columns:
                self._conn.execute(f"ALTER TABLE documents ADD COLUMN {name} {definition}")
        self._conn.commit()

    def add_document(self, document_id: str, kind: str, source: str, title: str = "", published_at: str = "", text: str = "", entities: list[dict[str, str]] | None = None, sha256: str = "", retrieved_at: str = "", metadata: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO documents(document_id,kind,title,published_at,source,text,sha256,retrieved_at,metadata) VALUES (?,?,?,?,?,?,?,?,?)",
            (document_id, kind, title, published_at, source, text, sha256, retrieved_at, json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
        )
        self._conn.execute("DELETE FROM document_entities WHERE document_id=?", (document_id,))
        for entity in entities or []:
            self._conn.execute("INSERT OR REPLACE INTO document_entities VALUES (?,?,?)", (document_id, entity.get("name", ""), entity.get("type", "")))
        self._conn.commit()

    def documents_for_entity(self, entity: str, kind: str | None = None) -> list[dict[str, Any]]:
        clause = " AND d.kind=?" if kind else ""
        params: list[Any] = [entity]
        if kind: params.append(kind)
        rows = self._conn.execute("SELECT d.* FROM documents d JOIN document_entities e ON e.document_id=d.document_id WHERE e.entity=?" + clause + " ORDER BY d.published_at DESC", params).fetchall()
        return [self._decode_row(row) for row in rows]

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        try:
            result["metadata"] = json.loads(result.get("metadata") or "{}")
        except (TypeError, json.JSONDecodeError):
            result["metadata"] = {}
        return result

    def document_count(self) -> int:
        return int(self._conn.execute("SELECT count(*) FROM documents").fetchone()[0])

    def search(self, entity: str, query: str = "", kind: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Search ingested document text while retaining source metadata."""
        rows = self.documents_for_entity(entity, kind=kind)
        terms = [term.casefold() for term in query.split() if term.strip()]
        if terms:
            rows = [row for row in rows if all(
                term in ((row.get("title") or "") + " " + (row.get("text") or "")).casefold()
                for term in terms
            )]
        for row in rows:
            text = row.get("text") or ""
            row["excerpt"] = text[:1200]
        return rows[:max(1, min(int(limit), 50))]

    def ingest_jsonl(self, path: str | Path) -> int:
        """Ingest enriched document records produced by the data loader."""
        count = 0
        with Path(path).open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                record = json.loads(line)
                entities = [{"name": record["company"], "type": "company"}]
                entities.extend(record.get("entities") or [])
                self.add_document(
                    str(record["document_id"]),
                    str(record.get("kind", "announcement")),
                    str(record["source"]),
                    title=str(record.get("title", "")),
                    published_at=str(record.get("published_at", "")),
                    text=str(record.get("text", "")),
                    entities=entities,
                    sha256=str(record.get("sha256", "")),
                    retrieved_at=str(record.get("retrieved_at", "")),
                    metadata={key: record[key] for key in ("pages", "page_count", "url") if key in record},
                )
                count += 1
        return count

    def related_entities(self, document_id: str) -> list[dict[str, str]]:
        rows = self._conn.execute("SELECT entity, entity_type FROM document_entities WHERE document_id=? ORDER BY entity", (document_id,)).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
