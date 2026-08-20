from jrkj.observability import RunStore


def test_run_store_appends_and_retrieves_latest_run(tmp_path):
    store = RunStore(tmp_path / "runs.jsonl")
    store.save({"run_id": "r1", "question": "first"})
    store.save({"run_id": "r1", "question": "latest"})
    store.save({"run_id": "r2", "question": "second"})
    assert store.get("r1")["question"] == "latest"
    assert [row["run_id"] for row in store.list()] == ["r2", "r1", "r1"]
