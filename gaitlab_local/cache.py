"""Validated, atomically-updated filesystem cache for extracted poses."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from gaitlab.core.schema import PoseSequence, VIEWS


class InvalidPoseCache(ValueError):
    """A cached or newly extracted pose file is not valid pose JSON."""


class PoseCache:
    """Store one normalized pose artifact per video stem and camera view.

    The requested view changes how the extractor interprets image coordinates, so it is
    part of the cache identity. Fresh extraction always targets a temporary file; only a
    parsed and validated pose is promoted to the stable path, so timeout/failure cannot
    poison a previously good cache.
    """

    def __init__(self, pose_dir: str | Path) -> None:
        self.pose_dir = Path(pose_dir)

    @staticmethod
    def _validate_stem(stem: str) -> str:
        if not stem or Path(stem).name != stem or stem in {".", ".."}:
            raise ValueError(f"invalid video stem: {stem!r}")
        return stem

    @staticmethod
    def _validate_view(view: str) -> str:
        if view not in VIEWS:
            raise ValueError(f"view must be one of {VIEWS}")
        return view

    def path_for(self, stem: str, view: str) -> Path:
        return self.pose_dir / (
            f"{self._validate_stem(stem)}.{self._validate_view(view)}.pose.json"
        )

    def legacy_path_for(self, stem: str) -> Path:
        """Return the pre-view-key cache path used before this boundary split."""
        return self.pose_dir / f"{self._validate_stem(stem)}.pose.json"

    def exists(self, stem: str, view: str) -> bool:
        return self.path_for(stem, view).is_file() or self.legacy_path_for(stem).is_file()

    def has_any(self, stem: str) -> bool:
        return self.legacy_path_for(stem).is_file() or any(
            self.path_for(stem, view).is_file() for view in VIEWS
        )

    def load(self, stem: str, view: str) -> PoseSequence:
        path = self.path_for(stem, view)
        if not path.is_file():
            path = self.legacy_path_for(stem)
        return self._load_path(path, view)

    @contextmanager
    def staging_path(self, stem: str, view: str) -> Iterator[Path]:
        self.pose_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = self._validate_stem(stem)
        safe_view = self._validate_view(view)
        fd, raw_path = tempfile.mkstemp(
            prefix=f".{safe_stem}.{safe_view}.",
            suffix=".pose.json.tmp",
            dir=self.pose_dir,
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
        destination = self.path_for(stem, view)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, destination)
        return sequence

    @staticmethod
    def _load_path(path: Path, view: str) -> PoseSequence:
        try:
            with path.open(encoding="utf-8") as handle:
                pose = json.load(handle)
            sequence = PoseSequence.from_pose_dict(pose).validate()
            if sequence.view != view:
                raise ValueError(
                    f"pose view {sequence.view!r} does not match requested view {view!r}"
                )
            return sequence
        except (OSError, TypeError, ValueError, KeyError, IndexError) as exc:
            raise InvalidPoseCache(f"invalid pose cache {path}: {exc}") from exc
