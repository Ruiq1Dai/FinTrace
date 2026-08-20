from jrkj.advanced_scores import altman_z_score, beneish_m_score, piotroski_f_score, peer_zscore
from jrkj.document_graph import DocumentGraph
from jrkj.self_evaluation import evaluate_artifact, repair_artifact


def test_scorecards_are_deterministic():
    assert beneish_m_score({"DSRI": 1, "GMI": 1, "AQI": 1, "SGI": 1, "DEPI": 1, "SGAI": 1, "LVGI": 1, "TATA": 0})["score"] == -2.48
    assert altman_z_score({"A": 1, "B": 1, "C": 1, "D": 1, "E": 1})["score"] == 7.5
    assert piotroski_f_score({key: True for key in ("roa_positive", "cfo_positive", "roa_improving", "accrual_quality", "leverage_improving", "liquidity_improving", "no_dilution", "margin_improving", "turnover_improving")})["score"] == 9
    assert peer_zscore(3, [1, 2, 3])["z_score"] == 1


def test_document_graph_entity_retrieval():
    graph = DocumentGraph()
    graph.add_document("a1", "announcement", "公告:a1", title="风险提示", entities=[{"name": "AAA", "type": "company"}])
    assert graph.documents_for_entity("AAA")[0]["document_id"] == "a1"
    assert graph.related_entities("a1")[0]["entity"] == "AAA"
    graph.close()


def test_document_graph_search_and_jsonl_ingest(tmpdir):
    path = tmpdir.join("docs.jsonl")
    path.write('{"document_id":"a2","company":"AAA","source":"url:a2","title":"处罚决定","published_at":20240501,"text":"收入确认问题"}\n')
    graph = DocumentGraph()
    assert graph.ingest_jsonl(path) == 1
    assert graph.search("AAA", "收入确认")[0]["document_id"] == "a2"
    graph.close()


def test_self_evaluation_flags_unsupported_citation():
    result = evaluate_artifact({"claims": ["收入增长"], "证据": ["missing"]}, ["income:AAA:2024"], [])
    assert result["repair_required"] is True
    assert result["unsupported_claim_rate"] == 1.0


def test_self_evaluation_repairs_unsupported_citations_without_inventing_sources():
    result = repair_artifact(
        {"结论": "收入存在变化", "证据": ["db#income", "invented#source"], "置信度": "high"},
        ["db#income:2024"],
    )
    assert result["repairable"] is True
    assert result["answer"]["证据"] == ["db#income"]
    assert result["answer"]["置信度"] == "medium"
    assert "invented#source" in result["removed_citations"]
