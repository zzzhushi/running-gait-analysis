"""Application use cases for the local GaitLab runtime."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from gaitlab import analyze, synthetic
from gaitlab.coaching import narrative
from gaitlab.core.schema import PoseSequence, PoseValidationError

from .ingest import VideoIngestor
from .repository import SQLiteRepository


class InvalidInput(ValueError):
    """A caller supplied an invalid application-level command."""


class NotFoundError(LookupError):
    """A requested local resource does not exist."""


class LocalApplication:
    """Coordinate the engine, local files, and persistence behind small use cases."""

    def __init__(
        self,
        repository: SQLiteRepository,
        ingestor: VideoIngestor,
        *,
        analyze_fn: Callable[..., Any] = analyze,
        demo_runs_fn: Callable[[], Iterable[tuple[str, PoseSequence, Mapping | None]]] = (
            synthetic.demo_runs
        ),
        narrative_fn: Callable[[dict], dict] = narrative.generate,
    ) -> None:
        self.repository = repository
        self.ingestor = ingestor
        self._analyze = analyze_fn
        self._demo_runs = demo_runs_fn
        self._narrative = narrative_fn

    # -- runs --------------------------------------------------------------
    def list_runs(self, user_id: str | None = None) -> list[dict]:
        return self.repository.list_runs(user_id)

    def get_run(self, run_id: str) -> dict | None:
        return self.repository.get_run(run_id)

    def delete_run(self, run_id: str) -> None:
        self.repository.delete_run(run_id)

    def analyze_pose(
        self,
        pose: Mapping[str, Any],
        *,
        label: str = "",
        profile: Mapping[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict:
        try:
            sequence = PoseSequence.from_pose_dict(dict(pose))
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise InvalidInput(f"invalid pose: {exc}") from exc
        return self.store_sequence(label, sequence, profile=profile, user_id=user_id)

    def store_sequence(
        self,
        label: str,
        sequence: PoseSequence,
        *,
        profile: Mapping[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict:
        try:
            result_obj = self._analyze(sequence, label=label, profile=profile)
        except PoseValidationError as exc:
            raise InvalidInput(str(exc)) from exc
        result = result_obj.to_dict() if hasattr(result_obj, "to_dict") else dict(result_obj)
        speed_kmh = (profile or {}).get("speed_kmh")
        run_id = self.repository.create_run(
            result, user_id=user_id, speed_kmh=speed_kmh
        )
        return {"id": run_id, "result": result}

    def seed_demo_runs(
        self,
        *,
        user_id: str | None = None,
        only_if_empty: bool = False,
    ) -> int:
        """Add missing demo runs without deleting or replacing user history.

        Interactive seeding targets the active user so the new runs appear in the
        library that requested them. Startup seeding omits ``user_id`` and uses the
        dedicated Demo profile.
        """
        if only_if_empty and self.repository.count_runs() != 0:
            return 0

        if user_id is not None:
            if self.repository.get_user(user_id) is None:
                raise NotFoundError("user not found")
        else:
            demo_user = self.repository.find_user_by_name("Demo")
            if demo_user is None:
                demo_user = self.repository.create_user("Demo")
            user_id = demo_user["id"]

        existing = self.repository.run_identities(user_id)
        added = 0
        for label, sequence, profile in self._demo_runs():
            identity = (label, sequence.view, sequence.source)
            if identity in existing:
                continue
            self.store_sequence(label, sequence, profile=profile, user_id=user_id)
            existing.add(identity)
            added += 1
        return added

    def generate_narrative(self, run_id: str) -> dict:
        run = self.repository.get_run(run_id)
        if run is None:
            raise NotFoundError("run not found")
        return self._narrative(run)

    # -- users -------------------------------------------------------------
    def list_users(self) -> list[dict]:
        return self.repository.list_users()

    def get_user(self, user_id: str) -> dict | None:
        return self.repository.get_user(user_id)

    def create_user(
        self,
        name: str,
        *,
        sex: str | None = None,
        height_cm: float | None = None,
        leg_length_cm: float | None = None,
    ) -> dict:
        if not isinstance(name, str) or not name.strip():
            raise InvalidInput("name is required")
        return self.repository.create_user(
            name.strip(), sex=sex, height_cm=height_cm, leg_length_cm=leg_length_cm
        )

    def update_user(self, user_id: str, updates: Mapping[str, Any]) -> dict | None:
        return self.repository.update_user(user_id, updates)

    def delete_user(self, user_id: str) -> None:
        self.repository.delete_user(user_id)

    # -- video / extraction ------------------------------------------------
    def list_videos(self) -> list[dict]:
        return self.ingestor.list_videos()

    def video_path(self, video_stem: str) -> Path:
        try:
            return self.ingestor.resolve_video(video_stem)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc

    def ingest_video(
        self,
        video_stem: str,
        view: str,
        *,
        force: bool = False,
        label: str = "",
        profile: Mapping[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict:
        try:
            ingested = self.ingestor.ingest(video_stem, view, force=force)
        except ValueError as exc:
            raise InvalidInput(str(exc)) from exc
        stored = self.store_sequence(
            label, ingested.sequence, profile=profile, user_id=user_id
        )
        stored.update(
            {
                "cached": ingested.cached,
                "video_stem": ingested.video_stem,
                "extractor_log": ingested.extractor_log,
            }
        )
        return stored
