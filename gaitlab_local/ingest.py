"""Video discovery and pose-extractor orchestration."""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from gaitlab.core.schema import PoseSequence, VIEWS

from .cache import InvalidPoseCache, PoseCache


class ExtractionError(RuntimeError):
    def __init__(self, message: str, log: str = "") -> None:
        super().__init__(message)
        self.log = log


class ExtractionTimeout(RuntimeError):
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(f"extraction timed out after {timeout_seconds:g}s")


@dataclass(frozen=True)
class IngestedPose:
    sequence: PoseSequence
    cached: bool
    video_stem: str
    extractor_log: str = ""


class VideoIngestor:
    """Resolve local videos and turn them into validated cached pose sequences."""

    def __init__(
        self,
        video_dir: str | Path,
        cache: PoseCache,
        extractor_path: str | Path,
        *,
        timeout_seconds: float = 600,
        python_executable: str = sys.executable,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.video_dir = Path(video_dir)
        self.cache = cache
        self.extractor_path = Path(extractor_path)
        self.timeout_seconds = timeout_seconds
        self.python_executable = python_executable
        self._runner = runner
        self._locks: dict[Path, threading.Lock] = {}
        self._locks_mutex = threading.Lock()

    def list_videos(self) -> list[dict]:
        self.video_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for path in self.video_dir.iterdir():
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
            items.append(
                {
                    "stem": path.stem,
                    "filename": path.name,
                    "mtime": datetime.fromtimestamp(
                        mtime, tz=timezone.utc
                    ).isoformat(timespec="seconds"),
                    "cached": self.cache.exists(path.stem),
                }
            )
        items.sort(key=lambda item: item["mtime"], reverse=True)
        return items

    def resolve_video(self, video_stem: str) -> Path:
        if not video_stem or Path(video_stem).name != video_stem or video_stem in {".", ".."}:
            raise ValueError(f"invalid video stem: {video_stem!r}")
        self.video_dir.mkdir(parents=True, exist_ok=True)
        candidates = sorted(
            (
                path
                for path in self.video_dir.iterdir()
                if path.is_file() and path.stem == video_stem
            ),
            key=lambda path: path.name,
        )
        if not candidates:
            raise FileNotFoundError(
                f"no video file for {video_stem!r} in {self.video_dir}"
            )
        return candidates[0]

    def ingest(self, video_stem: str, view: str, *, force: bool = False) -> IngestedPose:
        if view not in VIEWS:
            raise ValueError(f"view must be one of {VIEWS}")
        video_path = self.resolve_video(video_stem)
        cache_path = self.cache.path_for(video_stem)

        with self._lock_for(cache_path):
            if not force and self.cache.exists(video_stem):
                try:
                    sequence = self.cache.load(video_stem, view)
                    return IngestedPose(sequence, True, video_stem)
                except InvalidPoseCache:
                    # A cache is disposable. Re-extract without deleting it first so a
                    # failed repair cannot make the situation worse.
                    pass

            with self.cache.staging_path(video_stem) as staged_path:
                try:
                    completed = self._runner(
                        [
                            self.python_executable,
                            str(self.extractor_path),
                            str(video_path),
                            "--view",
                            view,
                            "--accurate",
                            "-o",
                            str(staged_path),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise ExtractionTimeout(self.timeout_seconds) from exc

                extractor_log = (completed.stderr or "").strip()
                if completed.returncode != 0:
                    raise ExtractionError("extractor failed", extractor_log)
                try:
                    sequence = self.cache.promote(staged_path, video_stem, view)
                except InvalidPoseCache as exc:
                    raise ExtractionError("extractor produced invalid pose", str(exc)) from exc

        return IngestedPose(sequence, False, video_stem, extractor_log)

    def _lock_for(self, cache_path: Path) -> threading.Lock:
        with self._locks_mutex:
            if cache_path not in self._locks:
                self._locks[cache_path] = threading.Lock()
            return self._locks[cache_path]
