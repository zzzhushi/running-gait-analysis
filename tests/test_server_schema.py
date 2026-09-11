"""Additive user-context migration preserves existing local data."""

import sqlite3

import server


def test_existing_v2_database_gets_context_columns_without_data_loss(tmp_path, monkeypatch):
    db_path = tmp_path / "gaitlab.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE _meta (v INTEGER)")
        conn.execute("INSERT INTO _meta VALUES (2)")
        conn.execute("""CREATE TABLE users (
            id TEXT PRIMARY KEY, created_at TEXT, name TEXT NOT NULL, sex TEXT,
            height_cm REAL, leg_length_cm REAL
        )""")
        conn.execute("INSERT INTO users VALUES ('existing', '2026-01-01', 'Runner', NULL, 160, 75)")

    monkeypatch.setattr(server, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(server, "DB_PATH", str(db_path))
    server._init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        existing = conn.execute("SELECT name, height_cm FROM users WHERE id='existing'").fetchone()
    assert {"age_years", "body_mass_kg"} <= columns
    assert existing == ("Runner", 160.0)



def test_retired_score_column_is_dropped_without_losing_run_history(tmp_path, monkeypatch):
    """Scoring is retired, so the column only accrues NULLs — but the runs beside it
    are the user's history and must survive. Deliberately not a SCHEMA_VERSION bump:
    _init_db is fail-closed on a version mismatch, so bumping would lock every
    existing database out of its own runs.
    """
    db_path = tmp_path / "gaitlab.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE _meta (v INTEGER)")
        conn.execute("INSERT INTO _meta VALUES (2)")
        conn.execute("""CREATE TABLE users (
            id TEXT PRIMARY KEY, created_at TEXT, name TEXT NOT NULL, sex TEXT,
            height_cm REAL, leg_length_cm REAL
        )""")
        conn.execute("""CREATE TABLE runs (
            id TEXT PRIMARY KEY, created_at TEXT, label TEXT, view TEXT, source TEXT,
            score REAL, grade TEXT, cadence REAL, n_findings INTEGER, speed_kmh REAL,
            user_id TEXT, result_json TEXT
        )""")
        conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("old1", "2025-01-01", "Legacy", "side-left", "rtmpose", 87.5, "B",
             172.0, 2, 12.0, None, '{"summary": {}}'),
        )

    monkeypatch.setattr(server, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(server, "DB_PATH", str(db_path))
    server._init_db()
    server._init_db()  # idempotent: the guard must not fire twice

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
        row = conn.execute("SELECT label, grade, cadence FROM runs WHERE id='old1'").fetchone()
    assert "score" not in columns
    assert row == ("Legacy", "B", 172.0)
    assert server.list_runs()[0]["id"] == "old1"


def test_new_databases_are_created_without_a_score_column(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "fresh.db"))
    server._init_db()
    with sqlite3.connect(tmp_path / "fresh.db") as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    assert "score" not in columns
    assert {"grade", "cadence", "result_json"} <= columns
