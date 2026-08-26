"""Persistence and application characterization tests for the local runtime."""

from __future__ import annotations

import json
import sqlite3

import pytest

from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab_local.application import LocalApplication
from gaitlab_local.repository import (
    SchemaError,
    SQLiteRepository,
    UnsupportedSchemaVersion,
)


def _sequence(*, source: str = "test") -> PoseSequence:
    point = (0.5, 0.5, 1.0)
    return PoseSequence(
        fps=30,
        width=640,
        height=480,
        view="side-left",
        frames=[[point for _ in KEYPOINTS]],
        source=source,
    )


def _result(label: str, sequence: PoseSequence) -> dict:
    return {
        "summary": {
            "label": label,
            "view": sequence.view,
            "source": sequence.source,
            "overall_score": 88.0,
            "grade": "B",
            "cadence": 172.0,
            "n_findings": 1,
        },
        "pose": sequence.to_pose_dict(),
    }


class _UnusedIngestor:
    pass


def test_repository_round_trips_runs_and_nulls_user_on_delete(tmp_path):
    identifiers = iter(("user-1", "run-1"))
    repository = SQLiteRepository(
        tmp_path / "nested" / "gaitlab.db",
        id_factory=lambda: next(identifiers),
        clock=lambda: "2026-01-02T03:04:05+00:00",
    )
    repository.initialize()

    user = repository.create_user("Runner", height_cm=170)
    result = _result("Morning run", _sequence())
    run_id = repository.create_run(result, user_id=user["id"], speed_kmh=12.5)

    # Startup is idempotent for an existing v2 database and must preserve rows.
    repository.initialize()

    assert run_id == "run-1"
    assert repository.get_run(run_id) == result
    assert repository.list_runs(user["id"])[0] == {
        "id": "run-1",
        "created_at": "2026-01-02T03:04:05+00:00",
        "label": "Morning run",
        "view": "side-left",
        "source": "test",
        "score": 88.0,
        "grade": "B",
        "cadence": 172.0,
        "n_findings": 1,
        "speed_kmh": 12.5,
        "user_id": "user-1",
    }

    repository.delete_user(user["id"])

    assert repository.get_user(user["id"]) is None
    assert repository.list_runs()[0]["user_id"] is None


def test_initialize_migrates_the_original_v1_schema_without_losing_runs(tmp_path):
    db_path = tmp_path / "gaitlab.db"
    legacy_result = _result("Legacy run", _sequence(source="legacy"))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                label TEXT,
                view TEXT,
                source TEXT,
                score REAL,
                grade TEXT,
                cadence REAL,
                n_findings INTEGER,
                result_json TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-1",
                "2025-01-01T00:00:00+00:00",
                "Legacy run",
                "side-left",
                "legacy",
                88.0,
                "B",
                172.0,
                1,
                json.dumps(legacy_result),
            ),
        )

    repository = SQLiteRepository(db_path)
    repository.initialize()

    assert repository.get_run("legacy-1") == legacy_result
    assert repository.list_runs()[0]["speed_kmh"] is None
    assert repository.list_runs()[0]["user_id"] is None
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT v FROM _meta").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_initialize_refuses_unknown_schema_without_deleting_its_data(tmp_path):
    db_path = tmp_path / "gaitlab.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE irreplaceable (value TEXT NOT NULL)")
        conn.execute("INSERT INTO irreplaceable VALUES ('keep me')")

    with pytest.raises(SchemaError, match="refusing to modify or delete"):
        SQLiteRepository(db_path).initialize()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT value FROM irreplaceable").fetchone()[0] == "keep me"


def test_initialize_refuses_a_future_version_without_deleting_its_data(tmp_path):
    db_path = tmp_path / "gaitlab.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE _meta (v INTEGER NOT NULL)")
        conn.execute("INSERT INTO _meta(v) VALUES (99)")
        conn.execute("CREATE TABLE future_data (value TEXT NOT NULL)")
        conn.execute("INSERT INTO future_data VALUES ('keep me too')")

    with pytest.raises(UnsupportedSchemaVersion, match="newer than supported"):
        SQLiteRepository(db_path).initialize()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT value FROM future_data").fetchone()[0] == "keep me too"


def test_demo_seed_is_additive_and_idempotent(tmp_path):
    identifiers = iter(("runner", "custom", "demo", "demo-run-1", "demo-run-2"))
    repository = SQLiteRepository(
        tmp_path / "gaitlab.db",
        id_factory=lambda: next(identifiers),
        clock=lambda: "2026-01-02T03:04:05+00:00",
    )
    repository.initialize()

    def analyze(sequence, *, label="", profile=None):
        return _result(label, sequence)

    demos = (
        ("Demo one", _sequence(source="demo-one"), None),
        ("Demo two", _sequence(source="demo-two"), {"speed_kmh": 10}),
    )
    application = LocalApplication(
        repository,
        _UnusedIngestor(),
        analyze_fn=analyze,
        demo_runs_fn=lambda: demos,
    )
    user = application.create_user("Runner")
    application.store_sequence("My run", _sequence(source="personal"), user_id=user["id"])

    assert application.seed_demo_runs() == 2
    assert application.seed_demo_runs() == 0

    runs = repository.list_runs()
    assert {run["label"] for run in runs} == {"My run", "Demo one", "Demo two"}
    assert repository.get_run("custom")["summary"]["label"] == "My run"
    assert repository.find_user_by_name("Demo") is not None


def test_startup_seed_preserves_the_original_seed_only_when_empty_contract(tmp_path):
    identifiers = iter(("runner", "custom"))
    repository = SQLiteRepository(
        tmp_path / "gaitlab.db", id_factory=lambda: next(identifiers)
    )
    repository.initialize()
    application = LocalApplication(
        repository,
        _UnusedIngestor(),
        analyze_fn=lambda sequence, *, label="", profile=None: _result(label, sequence),
        demo_runs_fn=lambda: (("Demo", _sequence(source="demo"), None),),
    )
    user = application.create_user("Runner")
    application.store_sequence("Existing", _sequence(), user_id=user["id"])

    assert application.seed_demo_runs(only_if_empty=True) == 0
    assert repository.find_user_by_name("Demo") is None
    assert repository.count_runs() == 1
