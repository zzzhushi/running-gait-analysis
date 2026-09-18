"""Composition-root tests for the machine-local server entry point."""

from __future__ import annotations

import server
from gaitlab_local.repository import UnsupportedSchemaVersion


def test_build_application_uses_injected_paths_without_seeding(tmp_path):
    application = server.build_application(
        db_path=tmp_path / "state" / "gaitlab.db",
        video_dir=tmp_path / "videos",
        pose_dir=tmp_path / "poses",
        extractor_path=tmp_path / "extract_pose.py",
        ingest_timeout=7,
    )

    assert application.repository.db_path == tmp_path / "state" / "gaitlab.db"
    assert application.repository.count_runs() == 0
    assert application.repository.list_users() == []
    assert application.ingestor.video_dir == tmp_path / "videos"
    assert application.ingestor.cache.pose_dir == tmp_path / "poses"
    assert application.ingestor.extractor_path == tmp_path / "extract_pose.py"
    assert application.ingestor.timeout_seconds == 7


def test_main_exits_with_a_schema_remediation_instead_of_a_traceback(monkeypatch):
    def fail_to_build():
        raise UnsupportedSchemaVersion(
            "database /tmp/gaitlab.db has schema version 99; this build requires version 2. "
            "Back it up and move it aside to start fresh."
        )

    monkeypatch.setattr(server, "build_application", fail_to_build)
    monkeypatch.setattr("sys.argv", ["server.py", "--no-open"])

    try:
        server.main()
    except SystemExit as exc:
        assert str(exc).startswith("GaitLab can't start:\n  database /tmp/gaitlab.db")
    else:
        raise AssertionError("server.main() did not exit")
