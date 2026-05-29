import json

from db import repository


def test_create_session_returns_uuid_and_persists(conn):
    sid = repository.create_session(conn, product_type="tricou", description="tricou navy cu logo")
    assert isinstance(sid, str) and len(sid) == 36

    row = repository.get_session(conn, sid)
    assert row["product_type"] == "tricou"
    assert row["initial_description"] == "tricou navy cu logo"
    assert row["status"] == "in_progress"
    assert row["rounds_used"] == 0
    assert json.loads(row["state_json"]) == {}
    assert json.loads(row["history_json"]) == []


def test_get_session_returns_none_when_missing(conn):
    assert repository.get_session(conn, "no-such-id") is None


def test_update_session_state_persists_state_history_and_rounds(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")
    new_state = {"culoare_principala": "albastru navy"}
    new_history = [{"round": 1, "questions": [], "answers": {}}]

    repository.update_session_state(conn, sid, new_state, new_history, rounds=1)
    row = repository.get_session(conn, sid)
    assert json.loads(row["state_json"]) == new_state
    assert json.loads(row["history_json"]) == new_history
    assert row["rounds_used"] == 1
    assert row["status"] == "in_progress"


def test_finalize_session_sets_status_and_completed_at(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")
    repository.finalize_session(conn, sid)
    row = repository.get_session(conn, sid)
    assert row["status"] == "complete"
    assert row["completed_at"] is not None


def test_save_report_returns_uuid_and_persists_all_fields(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")
    spec = {"culoare_principala": "navy"}
    image_paths = ["uploads/abc/img1.jpg"]
    conform = [{"camp": "culoare_principala", "valoare_asteptata": "navy",
                "valoare_observata": "navy", "incredere": "ridicat", "motiv": "vizibil"}]
    neconform, nevizibil = [], []
    raw = '{"conform":[...],"neconform":[],"nevizibil":[]}'

    rid = repository.save_report(conn, sid, spec, image_paths, conform, neconform, nevizibil, raw)
    assert len(rid) == 36

    row = repository.get_report(conn, rid)
    assert row["session_id"] == sid
    assert json.loads(row["spec_json"]) == spec
    assert json.loads(row["image_paths_json"]) == image_paths
    assert json.loads(row["conform_json"]) == conform


def test_get_report_returns_none_when_missing(conn):
    assert repository.get_report(conn, "no-such-id") is None


def test_create_match_session_returns_uuid_and_persists(conn):
    mid = repository.create_match_session(
        conn,
        sim_image_path="uploads/match/abc/sim.png",
        sim_report={"criteria": [{"id": "color", "label": "Color", "description": "navy"}]},
    )
    assert len(mid) == 36

    row = repository.get_match_session(conn, mid)
    assert row["sim_image_path"] == "uploads/match/abc/sim.png"
    assert row["real_image_path"] is None
    assert row["status"] == "awaiting_real"
    assert json.loads(row["sim_report_json"])["criteria"][0]["id"] == "color"
    assert row["compare_report_json"] is None


def test_get_match_session_returns_none_when_missing(conn):
    assert repository.get_match_session(conn, "no-such-id") is None


def test_update_match_compare_report_sets_real_path_status_and_report(conn):
    mid = repository.create_match_session(
        conn, sim_image_path="x/sim.png", sim_report={"criteria": []}
    )
    compare = {"rows": [{"criterion": "color", "match": True}], "summary": {"matched": 1}}
    repository.update_match_compare_report(
        conn, mid, real_image_path="x/real.png", compare_report=compare,
    )
    row = repository.get_match_session(conn, mid)
    assert row["real_image_path"] == "x/real.png"
    assert row["status"] == "complete"
    assert row["completed_at"] is not None
    assert json.loads(row["compare_report_json"]) == compare


def test_fail_match_session_sets_status(conn):
    mid = repository.create_match_session(
        conn, sim_image_path="x/sim.png", sim_report={"criteria": []}
    )
    repository.fail_match_session(conn, mid)
    row = repository.get_match_session(conn, mid)
    assert row["status"] == "failed"
