"""Filesystem-cache and extractor-boundary tests for local video ingestion."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab_local.cache import PoseCache
from gaitlab_local.ingest import ExtractionError, ExtractionTimeout, VideoIngestor


def _pose(*, source: str = "extractor") -> dict:
    point = (0.5, 0.5, 1.0)
    return PoseSequence(
        fps=30,
        width=640,
        height=480,
        view="side-left",
        frames=[[point for _ in KEYPOINTS]],
        source=source,
    ).to_pose_dict()


class _WritingRunner:
    def __init__(self, pose: dict, *, returncode: int = 0, stderr: str = "") -> None:
        self.pose = pose
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        assert kwargs == {
            "capture_output": True,
            "text": True,
            "timeout": 12,
        }
        output = Path(args[args.index("-o") + 1])
        output.write_text(json.dumps(self.pose), encoding="utf-8")
        return subprocess.CompletedProcess(
            args, self.returncode, stdout="", stderr=self.stderr
        )


def _ingestor(tmp_path, runner) -> tuple[VideoIngestor, PoseCache]:
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    (video_dir / "morning.run.mp4").write_bytes(b"video")
    cache = PoseCache(tmp_path / "pose")
    return (
        VideoIngestor(
            video_dir,
            cache,
            tmp_path / "extract_pose.py",
            timeout_seconds=12,
            python_executable="test-python",
            runner=runner,
        ),
        cache,
    )


def test_ingest_promotes_valid_output_then_reuses_the_cache(tmp_path):
    runner = _WritingRunner(_pose())
    ingestor, cache = _ingestor(tmp_path, runner)

    first = ingestor.ingest("morning.run", "side-left")
    second = ingestor.ingest("morning.run", "rear")

    assert first.cached is False
    assert first.video_stem == "morning.run"
    assert first.sequence.source == "extractor"
    assert second.cached is True
    assert second.sequence.view == "rear"
    assert len(runner.calls) == 1
    assert runner.calls[0][:2] == ["test-python", str(tmp_path / "extract_pose.py")]
    assert cache.path_for("morning.run").is_file()
    assert ingestor.list_videos()[0].keys() == {"stem", "filename", "mtime", "cached"}
    assert ingestor.list_videos()[0]["cached"] is True


def test_failed_forced_extraction_cannot_overwrite_a_good_cache(tmp_path):
    successful = _WritingRunner(_pose(source="good"))
    ingestor, cache = _ingestor(tmp_path, successful)
    ingestor.ingest("morning.run", "side-left")
    original = cache.path_for("morning.run").read_bytes()

    failed = _WritingRunner(
        {"not": "a pose"}, returncode=3, stderr="model failed"
    )
    retry = VideoIngestor(
        ingestor.video_dir,
        cache,
        ingestor.extractor_path,
        timeout_seconds=12,
        python_executable="test-python",
        runner=failed,
    )

    with pytest.raises(ExtractionError, match="extractor failed") as error:
        retry.ingest("morning.run", "side-left", force=True)

    assert error.value.log == "model failed"
    assert cache.path_for("morning.run").read_bytes() == original
    assert cache.load("morning.run", "side-left").source == "good"


def test_corrupt_cache_is_repaired_only_after_valid_extraction(tmp_path):
    runner = _WritingRunner(_pose(source="repaired"))
    ingestor, cache = _ingestor(tmp_path, runner)
    cache.pose_dir.mkdir()
    cache.path_for("morning.run").write_text(
        '{"frames": [[[]]]}', encoding="utf-8"
    )

    result = ingestor.ingest("morning.run", "side-left")

    assert result.cached is False
    assert result.sequence.source == "repaired"
    assert len(runner.calls) == 1


def test_timeout_is_translated_to_a_stable_application_error(tmp_path):
    def timeout_runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("extractor", 12)

    ingestor, cache = _ingestor(tmp_path, timeout_runner)

    with pytest.raises(ExtractionTimeout, match="timed out after 12s"):
        ingestor.ingest("morning.run", "side-left")

    assert not cache.exists("morning.run")
