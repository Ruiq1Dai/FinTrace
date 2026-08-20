import sqlite3

from jrkj.ownership_graph import OwnershipGraph


def make_db(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE shareholders (s_info_windcode TEXT, s_holder_name TEXT, s_holder_pct REAL, s_holder_enddate INTEGER)")
        db.executemany("INSERT INTO shareholders VALUES (?, ?, ?, ?)", [
            ("A", "H", 60, 20231231), ("B", "H", 20, 20231231),
            ("B", "X", 40, 20231231), ("C", "X", 55, 20231231),
        ])


def test_common_shareholder_and_two_hop_path(tmpdir):
    path = tmpdir.join("g.sqlite")
    make_db(path)
    graph = OwnershipGraph(path, end_date=20231231)
    assert graph.common_shareholders("A", "B")[0]["holder"] == "H"
    paths = graph.paths("A", "C", max_hops=4)
    assert len(paths) == 1
    assert [edge["holder"] for edge in paths[0]] == ["H", "H", "X", "X"]


def test_cycle_detection(tmpdir):
    path = tmpdir.join("cycle.sqlite")
    make_db(path)
    graph = OwnershipGraph(path, end_date=20231231)
    assert graph.circular_ownership(max_hops=3)


def test_terminal_controller_candidate_and_temporal_paths(tmpdir):
    path = tmpdir.join("temporal.sqlite")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE shareholders (s_info_windcode TEXT, s_holder_name TEXT, s_holder_pct REAL, s_holder_enddate INTEGER)")
        db.executemany("INSERT INTO shareholders VALUES (?, ?, ?, ?)", [
            ("A", "H", 60, 20231231), ("A", "H", 55, 20241231),
            ("B", "H", 20, 20231231),
        ])
    graph = OwnershipGraph(path, end_date=20231231)
    controllers = graph.ultimate_controllers("A")
    assert controllers[0]["controller"] == "H"
    assert controllers[0]["candidate_type"] == "terminal_holder"
    assert graph.temporal_paths("A", "B", max_hops=2).keys() == {"20231231"}
    changes = OwnershipGraph(path).ownership_changes("A")
    assert changes[0]["status"] == "changed"
