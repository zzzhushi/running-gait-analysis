"""Persistence invariants: startup and demo seeding must never delete run history.

Each test uses a throwaway database through the overridable `server.DB_PATH`.
"""

from __future__ import annotations

import sqlite3

import pytest

import server


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Point server at a fresh database and initialize it."""
    monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "test.db"))
    server._init_db()
    return server.DB_PATH


def _count(where: str = "", args=()) -> int:
    with server.db() as conn:
        return conn.execute(f"SELECT COUNT(*) AS c FROM runs {where}", args).fetchone()["c"]


class TestSeedingIsScopedAndAdditive:
    def test_seeding_one_profile_leaves_another_profiles_runs_alone(self, db):
        bob = server.create_user("Bob")["id"]
        server.store_run("Bob's run", server.synthetic.generate(duration=4), user_id=bob)
        alice = server.create_user("Alice")["id"]

        server.seed_demo_runs(alice)

        assert _count("WHERE user_id=?", (bob,)) == 1

    def test_seeding_puts_the_demos_on_the_profile_that_asked(self, db):
        alice = server.create_user("Alice")["id"]

        added = server.seed_demo_runs(alice)

        assert added == 3
        assert _count("WHERE user_id=?", (alice,)) == 3

    def test_seeding_twice_adds_nothing_the_second_time(self, db):
        alice = server.create_user("Alice")["id"]
        server.seed_demo_runs(alice)

        assert server.seed_demo_runs(alice) == 0
        assert _count("WHERE user_id=?", (alice,)) == 3

    def test_seeding_with_no_profile_creates_and_uses_demo(self, db):
        server.seed_demo_runs()

        with server.db() as conn:
            demo = conn.execute("SELECT id FROM users WHERE name='Demo'").fetchone()
        assert demo is not None
        assert _count("WHERE user_id=?", (demo["id"],)) == 3

    def test_seed_if_empty_does_nothing_when_any_run_exists(self, db):
        """First-launch convenience only — it must not re-seed a used database."""
        bob = server.create_user("Bob")["id"]
        server.store_run("Bob's run", server.synthetic.generate(duration=4), user_id=bob)

        server.seed_if_empty()

        assert _count() == 1


class TestSchemaVersionFailsClosed:
    def test_version_mismatch_raises_and_keeps_the_data(self, db):
        server.store_run("keep me", server.synthetic.generate(duration=4))
        with server.db() as conn:
            conn.execute("UPDATE _meta SET v=?", (server.SCHEMA_VERSION - 1,))

        with pytest.raises(server.SchemaVersionError, match="schema version"):
            server._init_db()

        assert _count() == 1

    def test_missing_meta_on_a_populated_db_raises_and_keeps_the_data(self, db):
        server.store_run("keep me", server.synthetic.generate(duration=4))
        with server.db() as conn:
            conn.execute("DROP TABLE _meta")

        with pytest.raises(server.SchemaVersionError, match="damaged"):
            server._init_db()

        assert _count() == 1

    def test_error_message_names_the_file_and_both_versions(self, db):
        with server.db() as conn:
            conn.execute("UPDATE _meta SET v=?", (server.SCHEMA_VERSION - 1,))

        with pytest.raises(server.SchemaVersionError) as exc:
            server._init_db()

        msg = str(exc.value)
        assert server.DB_PATH in msg
        assert str(server.SCHEMA_VERSION) in msg


class TestInitStillWorks:
    def test_fresh_database_initializes_at_the_current_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "fresh.db"))

        server._init_db()

        with server.db() as conn:
            assert conn.execute("SELECT v FROM _meta").fetchone()["v"] == server.SCHEMA_VERSION

    def test_init_is_idempotent_and_preserves_runs(self, db):
        server.store_run("keep me", server.synthetic.generate(duration=4))

        server._init_db()

        assert _count() == 1

    def test_init_creates_the_parent_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "nested" / "dir" / "g.db"))

        server._init_db()

        assert sqlite3.connect(server.DB_PATH).execute("SELECT v FROM _meta").fetchone()
