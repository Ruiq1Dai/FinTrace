from scripts.run_evaluation import run_evaluation


def test_ablation_has_expected_variants_without_graph():
    result = run_evaluation(enable_graph=False)
    names = [row["variant"] for row in result["variants"]]
    assert names == ["llm_only", "retrieval", "retrieval_calculation", "retrieval_calculation_graph", "full_system"]
    assert result["variants"][1]["metrics"]["answer_accuracy"] == 1.0
    assert result["variants"][-1]["metrics"]["unsupported_claim_rate"] == 0.0
