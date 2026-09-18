"""Composition-root tests for the machine-local server entry point."""

from __future__ import annotations

import server


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
