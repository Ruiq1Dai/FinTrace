from jrkj.risk_thresholds import DEFAULT_THRESHOLDS, get_threshold


def test_default_thresholds_are_explicit_and_overridable():
    assert get_threshold("beneish_m_score") == -1.78
    assert get_threshold("beneish_m_score", {"beneish_m_score": -2.0}) == -2.0
    assert DEFAULT_THRESHOLDS["altman_distress"] < DEFAULT_THRESHOLDS["altman_grey"]


def test_neo4j_driver_is_lazy():
    from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph
    class Driver:
        def close(self): pass
    graph = Neo4jOwnershipGraph("bolt://unused", "u", "p", driver=Driver())
    graph.close()


def test_neo4j_batch_size_validation():
    from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph
    class Driver:
        def close(self): pass
    graph = Neo4jOwnershipGraph("bolt://unused", "u", "p", driver=Driver())
    try:
        graph.upsert_edges([], batch_size=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid batch size should fail")


def test_neo4j_edge_upsert_deduplicates_source_rows():
    from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph

    class Result:
        def single(self): return {"count": 1}
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def run(self, query, **kwargs):
            assert len(kwargs["rows"]) == 1
            return Result()
    class Driver:
        def session(self, **kwargs): return Session()
        def close(self): pass

    graph = Neo4jOwnershipGraph("bolt://unused", "u", "p", driver=Driver())
    rows = [
        {"company": "a", "holder": " H ", "period": 20240101, "pct": 1, "source": "s1"},
        {"company": "A", "holder": "H", "period": "20240101", "pct": 2, "source": "s2"},
    ]
    assert graph.upsert_edges(rows) == 1


def test_neo4j_entity_upsert_preserves_verification_status():
    from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph

    class Result:
        def single(self): return {"count": 2}
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def run(self, query, **kwargs):
            assert "verification_status" in query
            assert len(kwargs["rows"]) == 2
            return Result()
    class Driver:
        def session(self, **kwargs): return Session()
        def close(self): pass

    graph = Neo4jOwnershipGraph("bolt://unused", "u", "p", driver=Driver())
    rows = [
        {"entity_id": "security:A", "entity_type": "company", "security_code": "A", "canonical_name": "A", "aliases": ["A"], "verification_status": "verified_security_code", "effective_period": "2024", "source": "s"},
        {"entity_id": "holder:x", "entity_type": "holder", "canonical_name": "X", "aliases": ["X"], "verification_status": "unresolved_name_match", "effective_period": "2024", "source": "s", "company_scope": ["A"], "limitations": ["name-only"]},
    ]
    assert graph.upsert_entities(rows) == 2


def test_neo4j_resolution_upsert_requires_a_source_in_query():
    from jrkj.neo4j_ownership_graph import Neo4jOwnershipGraph

    class Result:
        def single(self): return {"count": 1}
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def run(self, query, **kwargs):
            assert "RESOLVED_AS" in query
            assert "verification_source" in query
            return Result()
    class Driver:
        def session(self, **kwargs): return Session()
        def close(self): pass

    graph = Neo4jOwnershipGraph("bolt://unused", "u", "p", driver=Driver())
    assert graph.upsert_resolutions([{"holder_name": "H", "security_code": "A", "verification_status": "verified_external_source", "verification_source": "registry#A"}]) == 1


def test_neo4j_graph_mode_does_not_fallback(monkeypatch):
    from agent import graph_traversal
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    try:
        graph_traversal("common_shareholders", "600238.SH", "000955.SZ", "", 3, backend_mode="neo4j")
    except RuntimeError as exc:
        assert "NEO4J_URI" in str(exc)
    else:
        raise AssertionError("Neo4j graph mode must fail without Neo4j credentials")
