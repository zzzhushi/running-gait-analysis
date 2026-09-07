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

