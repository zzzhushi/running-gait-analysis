"""Validated, atomically-updated filesystem cache for extracted poses."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from gaitlab.core.schema import PoseSequence


class InvalidPoseCache(ValueError):
    """A cached or newly extracted pose file is not valid pose JSON."""


class PoseCache:
    """Store one normalized pose artifact per video stem.

    Cache identity remains stem-based for compatibility with the existing browser API.
    Fresh extraction always targets a temporary file; only a parsed and validated pose is
    promoted to the stable path, so timeout/failure cannot poison a previously good cache.
    """

    def __init__(self, pose_dir: str | Path) -> None:
        self.pose_dir = Path(pose_dir)

    @staticmethod
    def _validate_stem(stem: str) -> str:
        if not stem or Path(stem).name != stem or stem in {".", ".."}:
            raise ValueError(f"invalid video stem: {stem!r}")
        return stem

    def path_for(self, stem: str) -> Path:
        return self.pose_dir / f"{self._validate_stem(stem)}.pose.json"

    def exists(self, stem: str) -> bool:
        return self.path_for(stem).is_file()

    def load(self, stem: str, view: str) -> PoseSequence:
        return self._load_path(self.path_for(stem), view)

    @contextmanager
    def staging_path(self, stem: str) -> Iterator[Path]:
        self.pose_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = self._validate_stem(stem)
        fd, raw_path = tempfile.mkstemp(
            prefix=f".{safe_stem}.", suffix=".pose.json.tmp", dir=self.pose_dir
        )
        os.close(fd)
        path = Path(raw_path)
        try:
            yield path
        finally:
            path.unlink(missing_ok=True)

    def promote(self, staged_path: str | Path, stem: str, view: str) -> PoseSequence:
        staged = Path(staged_path)
        sequence = self._load_path(staged, view)
        destination = self.path_for(stem)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, destination)
        return sequence

    @staticmethod
    def _load_path(path: Path, view: str) -> PoseSequence:
        try:
            with path.open(encoding="utf-8") as handle:
                pose = json.load(handle)
            pose["view"] = view
            return PoseSequence.from_pose_dict(pose).validate()
        except (OSError, TypeError, ValueError, KeyError, IndexError) as exc:
            raise InvalidPoseCache(f"invalid pose cache {path}: {exc}") from exc
