import json
import sqlite3
import uuid


def create_session(conn: sqlite3.Connection, product_type: str, description: str) -> str:
    sid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO discovery_sessions
            (id, product_type, initial_description, state_json, history_json, status)
        VALUES (?, ?, ?, ?, ?, 'in_progress')
        """,
        (sid, product_type, description, "{}", "[]"),
    )
    conn.commit()
    return sid


def get_session(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM discovery_sessions WHERE id = ?", (session_id,))
    return cur.fetchone()


def update_session_state(conn: sqlite3.Connection, session_id: str,
                         state: dict, history: list, rounds: int) -> None:
    conn.execute(
        """
        UPDATE discovery_sessions
        SET state_json = ?, history_json = ?, rounds_used = ?
        WHERE id = ?
        """,
        (json.dumps(state, ensure_ascii=False),
         json.dumps(history, ensure_ascii=False),
         rounds, session_id),
    )
    conn.commit()


def finalize_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        """
        UPDATE discovery_sessions
        SET status = 'complete', completed_at = datetime('now')
        WHERE id = ?
        """,
        (session_id,),
    )
    conn.commit()


def save_report(conn: sqlite3.Connection, session_id: str, spec: dict, image_paths: list,
                conform: list, neconform: list, nevizibil: list, raw: str) -> str:
    rid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO validation_reports
            (id, session_id, spec_json, image_paths_json,
             conform_json, neconform_json, nevizibil_json, raw_llm_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (rid, session_id,
         json.dumps(spec, ensure_ascii=False),
         json.dumps(image_paths, ensure_ascii=False),
         json.dumps(conform, ensure_ascii=False),
         json.dumps(neconform, ensure_ascii=False),
         json.dumps(nevizibil, ensure_ascii=False),
         raw),
    )
    conn.commit()
    return rid


def get_report(conn: sqlite3.Connection, report_id: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM validation_reports WHERE id = ?", (report_id,))
    return cur.fetchone()


def create_match_session(conn: sqlite3.Connection, sim_image_path: str, sim_report: dict) -> str:
    mid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO match_sessions
            (id, sim_image_path, sim_report_json, status)
        VALUES (?, ?, ?, 'awaiting_real')
        """,
        (mid, sim_image_path, json.dumps(sim_report, ensure_ascii=False)),
    )
    conn.commit()
    return mid


def get_match_session(conn: sqlite3.Connection, match_id: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM match_sessions WHERE id = ?", (match_id,))
    return cur.fetchone()


def update_match_sim(conn: sqlite3.Connection, match_id: str,
                     sim_image_path: str, sim_report: dict) -> None:
    """Replace the mockup image + its extracted criteria (status unchanged)."""
    conn.execute(
        "UPDATE match_sessions SET sim_image_path = ?, sim_report_json = ? WHERE id = ?",
        (sim_image_path, json.dumps(sim_report, ensure_ascii=False), match_id),
    )
    conn.commit()


def update_match_compare_report(conn: sqlite3.Connection, match_id: str,
                                real_image_path: str, compare_report: dict) -> None:
    conn.execute(
        """
        UPDATE match_sessions
        SET real_image_path = ?, compare_report_json = ?,
            status = 'complete', completed_at = datetime('now')
        WHERE id = ?
        """,
        (real_image_path,
         json.dumps(compare_report, ensure_ascii=False),
         match_id),
    )
    conn.commit()


def fail_match_session(conn: sqlite3.Connection, match_id: str) -> None:
    conn.execute(
        "UPDATE match_sessions SET status = 'failed' WHERE id = ?",
        (match_id,),
    )
    conn.commit()
