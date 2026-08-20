"""Versioned, provenance-preserving evidence memory for JRKJ."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database import DEFAULT_DB


DEFAULT_MEMORY_DB = Path(__file__).resolve().parents[2] / "database" / "jrkj_memory.sqlite3"


def dataset_version(db_path: Path = DEFAULT_DB) -> str:
    stat = Path(db_path).stat()
    raw = f"{Path(db_path).resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class PersistentEvidenceMemory:
    """A write-through ledger of exact tool evidence, never model-generated facts."""

    def __init__(
        self,
        path: Path = DEFAULT_MEMORY_DB,
        source_db: Path = DEFAULT_DB,
    ) -> None:
        self.path = Path(path)
        self.source_db = Path(source_db)
        self.version = dataset_version(self.source_db)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence_memory (
                    evidence_id TEXT PRIMARY KEY,
                    dataset_version TEXT NOT NULL,
                    company TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    period_field TEXT NOT NULL,
                    period INTEGER NOT NULL,
                    values_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_lookup
                ON evidence_memory(dataset_version, company, table_name, period DESC);
                """
            )
        self._consolidate_current_version()

    def _consolidate_current_version(self) -> None:
        """Migrate older field-shaped entries to one row per original source."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence_memory WHERE dataset_version=? ORDER BY observed_at",
                (self.version,),
            ).fetchall()
            grouped: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                item = grouped.setdefault(row["source"], dict(row))
                values = json.loads(item["values_json"])
                values.update(json.loads(row["values_json"]))
                item["values_json"] = json.dumps(values, ensure_ascii=False, sort_keys=True)
                item["observed_at"] = max(item["observed_at"], row["observed_at"])
            if len(grouped) == len(rows):
                return
            connection.execute(
                "DELETE FROM evidence_memory WHERE dataset_version=?", (self.version,)
            )
            for source, item in grouped.items():
                evidence_id = hashlib.sha256(
                    (self.version + ":" + source).encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    INSERT INTO evidence_memory
                    (evidence_id, dataset_version, company, table_name, period_field,
                     period, values_json, source, observed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id, self.version, item["company"], item["table_name"],
                        item["period_field"], item["period"], item["values_json"],
                        source, item["observed_at"],
                    ),
                )

    def remember_query(self, result: Dict[str, Any]) -> int:
        observed_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        rows = []
        for item in result.get("evidence", []):
            evidence_id = hashlib.sha256(
                (self.version + ":" + item["source"]).encode("utf-8")
            ).hexdigest()
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT values_json FROM evidence_memory WHERE evidence_id=?",
                    (evidence_id,),
                ).fetchone()
            values = json.loads(existing[0]) if existing else {}
            values.update(item["values"])
            rows.append(
                (
                    evidence_id,
                    self.version,
                    item["company"],
                    item["table"],
                    item["period_field"],
                    int(item["period"]),
                    json.dumps(values, ensure_ascii=False, sort_keys=True),
                    item["source"],
                    observed_at,
                )
            )
        if rows:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO evidence_memory
                    (evidence_id, dataset_version, company, table_name, period_field,
                     period, values_json, source, observed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        return len(rows)

    def recall(
        self,
        company: str,
        table_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conditions = ["dataset_version=?", "company=?"]
        parameters: List[Any] = [self.version, company.upper()]
        if table_name:
            conditions.append("table_name=?")
            parameters.append(table_name)
        parameters.append(max(1, min(int(limit), 100)))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT company, table_name, period_field, period, values_json,
                       source, observed_at
                FROM evidence_memory
                WHERE {' AND '.join(conditions)}
                ORDER BY period DESC, table_name, source
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [
            {
                "company": row["company"],
                "table": row["table_name"],
                "period_field": row["period_field"],
                "period": row["period"],
                "values": json.loads(row["values_json"]),
                "source": row["source"],
                "observed_at": row["observed_at"],
                "dataset_version": self.version,
            }
            for row in rows
        ]
