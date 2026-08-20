"""Neo4j-backed ownership graph for the full graph execution profile."""
from __future__ import annotations

from typing import Any, Iterable


class Neo4jOwnershipGraph:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j", driver: Any = None) -> None:
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:
                raise RuntimeError("Neo4j support requires the optional 'neo4j' package") from exc
            driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver, self.database = driver, database

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> bool:
        """Fail fast when the configured Neo4j graph is unavailable."""
        with self.driver.session(database=self.database) as session:
            record = session.run("RETURN 1 AS ok").single()
        return bool(record and record["ok"] == 1)

    def ensure_schema(self) -> None:
        """Create idempotent constraints for the JRKJ ownership subgraph."""
        statements = (
            "CREATE CONSTRAINT jrkj_company_code IF NOT EXISTS FOR (c:Company) REQUIRE c.code IS UNIQUE",
            "CREATE CONSTRAINT jrkj_holder_name IF NOT EXISTS FOR (h:Holder) REQUIRE h.name IS UNIQUE",
        )
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()

    def upsert_edges(self, edges: Iterable[dict[str, Any]], batch_size: int = 500) -> int:
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in edges:
            row = dict(item)
            key = (str(row["company"]).upper(), str(row["holder"]).strip(), str(row["period"]))
            row["company"], row["holder"], row["period"] = key
            unique[key] = row
        rows = list(unique.values())
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        query = ("UNWIND $rows AS row MERGE (c:Company {code: row.company}) "
                 "MERGE (h:Holder {name: row.holder}) "
                 "MERGE (h)-[r:OWNS {period: row.period}]->(c) "
                 "SET r.pct=row.pct, r.source=row.source RETURN count(r) AS count")
        imported = 0
        with self.driver.session(database=self.database) as session:
            for start in range(0, len(rows), batch_size):
                record = session.run(query, rows=rows[start:start + batch_size]).single()
                imported += int(record["count"]) if record else 0
        return imported

    def upsert_entities(self, records: Iterable[dict[str, Any]], batch_size: int = 500) -> int:
        """Attach auditable identity metadata without resolving name-only holders."""
        rows = [dict(record) for record in records]
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        query = (
            "UNWIND $rows AS row "
            "FOREACH (_ IN CASE WHEN row.entity_type='company' THEN [1] ELSE [] END | "
            "MERGE (c:Company {code: row.security_code}) "
            "SET c.entity_id=row.entity_id, c.entity_type=row.entity_type, "
            "c.verification_status=row.verification_status, c.canonical_name=row.canonical_name, "
            "c.aliases=row.aliases, c.effective_period=row.effective_period, c.source=row.source) "
            "FOREACH (_ IN CASE WHEN row.entity_type='holder' THEN [1] ELSE [] END | "
            "MERGE (h:Holder {name: row.canonical_name}) "
            "SET h.entity_id=row.entity_id, h.entity_type=row.entity_type, "
            "h.verification_status=row.verification_status, h.aliases=row.aliases, "
            "h.effective_period=row.effective_period, h.source=row.source, "
            "h.company_scope=row.company_scope, h.limitations=row.limitations, "
            "h.resolved_entity_id=row.resolved_entity_id, h.resolved_security_code=row.resolved_security_code, "
            "h.verification_source=row.verification_source) "
            "RETURN count(*) AS count"
        )
        imported = 0
        with self.driver.session(database=self.database) as session:
            for start in range(0, len(rows), batch_size):
                record = session.run(query, rows=rows[start:start + batch_size]).single()
                imported += int(record["count"]) if record else 0
        return imported

    def upsert_resolutions(self, records: Iterable[dict[str, Any]], batch_size: int = 500) -> int:
        rows = [dict(row) for row in records]
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        query = (
            "UNWIND $rows AS row MATCH (h:Holder {name:row.holder_name}), (c:Company {code:row.security_code}) "
            "MERGE (h)-[r:RESOLVED_AS]->(c) SET r.source=row.verification_source, "
            "r.status=row.verification_status, r.effective_from=row.effective_from, "
            "r.effective_to=row.effective_to RETURN count(r) AS count"
        )
        imported = 0
        with self.driver.session(database=self.database) as session:
            for start in range(0, len(rows), batch_size):
                record = session.run(query, rows=rows[start:start + batch_size]).single()
                imported += int(record["count"]) if record else 0
        return imported

    def paths(
        self, start: str, target: str, max_hops: int = 3,
        period: str | int | None = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        if max_hops < 1 or max_hops > 12:
            raise ValueError("max_hops must be between 1 and 12")
        if period in (None, ""):
            raise ValueError("Neo4j path traversal requires an explicit shareholder snapshot period")
        query = ("MATCH p=(start:Company {code:$start})-[:OWNS*1.." + str(int(max_hops)) + " {period:$period}]-(target:Company {code:$target}) "
                 "RETURN [n IN nodes(p) | coalesce(n.code,n.name)] AS nodes, "
                 "[r IN relationships(p) | {holder:startNode(r).name,company:endNode(r).code,period:r.period,pct:r.pct,source:r.source}] AS edges "
                 "LIMIT $limit")
        with self.driver.session(database=self.database) as session:
            return [dict(record) for record in session.run(
                query, start=start.upper(), target=target.upper(), period=str(period),
                limit=max(1, min(int(limit), 500)),
            )]

    def common_shareholders(
        self, company_a: str, company_b: str, period: str | int | None = None,
    ) -> list[dict[str, Any]]:
        query = ("MATCH (a:Company {code:$a}), (b:Company {code:$b}) "
                 "CALL (a) { MATCH ()-[r:OWNS]->(a) RETURN max(r.period) AS latest_a } "
                 "CALL (b) { MATCH ()-[r:OWNS]->(b) RETURN max(r.period) AS latest_b } "
                 "MATCH (h:Holder)-[ra:OWNS]->(a), (h)-[rb:OWNS]->(b) "
                 "WHERE ($period='' AND ra.period=latest_a AND rb.period=latest_b) "
                 "OR ($period<>'' AND ra.period=$period AND rb.period=$period) "
                 "RETURN h.name AS holder, "
                 "{company:$a, period:ra.period, pct:ra.pct, source:ra.source} AS company_a, "
                 "{company:$b, period:rb.period, pct:rb.pct, source:rb.source} AS company_b "
                 "ORDER BY holder")
        with self.driver.session(database=self.database) as session:
            return [dict(record) for record in session.run(
                query, a=company_a.upper(), b=company_b.upper(),
                period="" if period in (None, "") else str(period),
            )]

    def ultimate_controllers(
        self, company: str, max_hops: int = 6, period: str | int | None = None,
    ) -> list[dict[str, Any]]:
        """Return direct holder candidates with auditable relationship fields."""
        if max_hops < 1 or max_hops > 12:
            raise ValueError("max_hops must be between 1 and 12")
        query = ("MATCH (c:Company {code:$company}) "
                 "CALL (c) { MATCH ()-[candidate:OWNS]->(c) RETURN max(candidate.period) AS latest } "
                 "MATCH (h:Holder)-[r:OWNS]->(c) "
                 "WHERE ($period='' AND r.period=latest) OR r.period=$period "
                 "RETURN h.name AS controller, h.resolved_entity_id AS resolved_entity_id, "
                 "[{holder:h.name, company:c.code, period:r.period, pct:r.pct, source:r.source}] AS path, "
                 "1 AS hops, 'terminal_holder' AS candidate_type ORDER BY controller")
        with self.driver.session(database=self.database) as session:
            return [dict(record) for record in session.run(
                query, company=company.upper(),
                period="" if period in (None, "") else str(period),
            )]

    def circular_ownership(self, max_hops: int = 6) -> list[dict[str, Any]]:
        if max_hops < 1 or max_hops > 12:
            raise ValueError("max_hops must be between 1 and 12")
        query = ("MATCH (h:Holder)-[:RESOLVED_AS]->(owner:Company), (h)-[r:OWNS]->(target:Company) "
                 "RETURN owner.code AS owner, target.code AS target, h.name AS holder, "
                 "r.period AS period, r.pct AS pct, r.source AS source")
        with self.driver.session(database=self.database) as session:
            edges = [dict(record) for record in session.run(query)]
        if not edges:
            raise RuntimeError(
                "Circular ownership requires resolved company-holder entity identities; "
                "exact-name shareholder snapshots are insufficient"
            )
        adjacency: dict[str, list[dict[str, Any]]] = {}
        for edge in edges:
            adjacency.setdefault(edge["owner"], []).append(edge)
        results: list[dict[str, Any]] = []
        def walk(start: str, current: str, path: list[dict[str, Any]], seen: set[str]) -> None:
            if len(path) >= max_hops:
                return
            for edge in adjacency.get(current, []):
                next_node = edge["target"]
                next_path = path + [edge]
                if next_node == start:
                    results.append({"cycle": [start] + [item["target"] for item in next_path], "edges": next_path, "hops": len(next_path)})
                elif next_node not in seen:
                    walk(start, next_node, next_path, seen | {next_node})
        for start in adjacency:
            walk(start, start, [], {start})
        unique: dict[tuple[str, ...], dict[str, Any]] = {}
        for result in results:
            cycle = tuple(result["cycle"])
            canonical = min(cycle[:-1]) if cycle else ""
            rotate = next((index for index, value in enumerate(cycle[:-1]) if value == canonical), 0)
            normalized = cycle[rotate:-1] + cycle[:rotate] + (canonical,)
            unique[normalized] = result
        return list(unique.values())
