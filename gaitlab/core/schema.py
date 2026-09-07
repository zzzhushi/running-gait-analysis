"""Normalized pose schema shared by every pose source (RTMPose, MediaPipe, synthetic).

Image coordinate convention: origin is the TOP-LEFT, +x points right, +y points DOWN.
So a point that is physically *higher off the ground* has a *smaller* y. Every helper
that reasons about height accounts for this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from statistics import median
from typing import List, Optional, Tuple

SCHEMA_VERSION = "gaitlab.pose/v1"


class PoseValidationError(ValueError):
    """Raised when a PoseSequence is structurally invalid (bad shape, ranges, or view)."""

# Canonical keypoint set: a superset that RTMPose-Halpe26 (26 kpts incl. 6 foot points)
# and MediaPipe-BlazePose (33 kpts) both map into. Order is fixed; arrays are aligned to it.
KEYPOINTS: List[str] = [
    "nose", "head", "neck", "mid_hip",
    "l_shoulder", "r_shoulder",
    "l_elbow", "r_elbow",
    "l_wrist", "r_wrist",
    "l_hip", "r_hip",
    "l_knee", "r_knee",
    "l_ankle", "r_ankle",
    "l_heel", "r_heel",
    "l_big_toe", "r_big_toe",
    "l_small_toe", "r_small_toe",
]
KP_INDEX = {name: i for i, name in enumerate(KEYPOINTS)}

VIEWS = ("side-left", "side-right", "rear", "front")

# (x, y, confidence)
Point = Tuple[float, float, float]
XY = Tuple[float, float]


@dataclass
class PoseSequence:
    """A time series of normalized landmarks for a single clip/view."""

    fps: float
    width: int
    height: int
    view: str
    frames: List[List[Point]]  # frames[f][kp_index] = (x, y, confidence)
    source: str = "unknown"
    keypoint_names: List[str] = field(default_factory=lambda: list(KEYPOINTS))
    # Real per-frame presentation timestamps in SECONDS, aligned to `frames`.
    # Present when the extractor could read them (robust to variable frame rate);
    # None for synthetic/constant-rate clips, where f/fps is exact.
    timestamps: Optional[List[float]] = None
    # Internal-only threshold used by the analysis copy. Raw sequences keep 0 so
    # serialization and the overlay retain every detector coordinate.
    analysis_min_confidence: float = field(default=0.0, repr=False)

    # --- validation -------------------------------------------------------
    def validate(self) -> "PoseSequence":
        """Check structural integrity; raise PoseValidationError listing every problem.

        Guards the analysis pipeline against malformed pose input (wrong frame shape,
        non-finite coordinates, confidence outside [0,1], unknown view). Returns self
        so it can be chained.
        """
        errs: List[str] = []
        if not isinstance(self.fps, (int, float)) or self.fps != self.fps or self.fps <= 0:
            errs.append(f"fps must be a positive number (got {self.fps!r})")
        if self.view not in VIEWS:
            errs.append(f"view must be one of {VIEWS} (got {self.view!r})")
        if not self.keypoint_names:
            errs.append("keypoint_names is empty")
        if not self.frames:
            errs.append("frames is empty")

        if self.timestamps is not None:
            if len(self.timestamps) != len(self.frames):
                errs.append(
                    f"timestamps has {len(self.timestamps)} entries, expected {len(self.frames)}"
                )
            elif any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in self.timestamps):
                errs.append("timestamps must be finite numbers")
            elif any(b <= a for a, b in zip(self.timestamps, self.timestamps[1:])):
                errs.append("timestamps must be strictly increasing")

        k = len(self.keypoint_names)
        for fi, fr in enumerate(self.frames):
            if len(fr) != k:
                errs.append(f"frame {fi} has {len(fr)} keypoints, expected {k}")
                break  # one shape error is enough; don't spam
            bad = None
            for pi, p in enumerate(fr):
                if len(p) < 3:
                    bad = f"kp {pi} is not (x, y, confidence)"
                    break
                x, y, c = p[0], p[1], p[2]
                if any(not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v)
                       for v in (x, y, c)):
                    bad = f"kp {pi} has a non-finite value {tuple(p[:3])}"
                    break
                # Real extractors (RTMPose/ONNX) occasionally emit scores slightly above
                # 1.0, so allow a small margin; only reject clearly-broken confidences.
                if c < 0.0 or c > 1.5:
                    bad = f"kp {pi} confidence {c} outside [0,1.5]"
                    break
            if bad:
                errs.append(f"frame {fi}: {bad}")
                break

        if errs:
            raise PoseValidationError("; ".join(errs))
        return self

    # --- basic info -------------------------------------------------------
    @property
    def n(self) -> int:
        return len(self.frames)

    @property
    def duration(self) -> float:
        if self.timestamps and len(self.timestamps) > 1:
            frame_period = (self.timestamps[-1] - self.timestamps[0]) / (len(self.timestamps) - 1)
            return self.timestamps[-1] - self.timestamps[0] + frame_period
        return self.n / self.fps if self.fps else 0.0

    @property
    def effective_fps(self) -> float:
        """Median observed sampling rate, falling back to nominal metadata."""
        if self.timestamps is not None and len(self.timestamps) > 1:
            intervals = [b - a for a, b in zip(self.timestamps, self.timestamps[1:])]
            frame_period = median(intervals)
            if frame_period > 0:
                return 1.0 / frame_period
        return self.fps

    def time_at(self, frame: int) -> float:
        """Presentation time in seconds, using real timestamps when available."""
        if self.timestamps is not None:
            return self.timestamps[frame]
        return frame / self.fps

    def elapsed(self, start: int, end: int) -> float:
        """Elapsed seconds between two frame indices."""
        return self.time_at(end) - self.time_at(start)

    def is_side(self) -> bool:
        return self.view in ("side-left", "side-right")

    def is_rear(self) -> bool:
        return self.view in ("rear", "front")

    def facing_sign(self) -> int:
        """+1 if the runner faces/moves toward +x, -1 toward -x (side views only).

        Inferred from the average horizontal offset of the toes ahead of the heels.
        """
        try:
            ti, hi = self.idx("l_big_toe"), self.idx("l_heel")
        except ValueError:
            return 1
        diffs = []
        for fr in self.frames:
            toe, heel = fr[ti], fr[hi]
            if toe[2] > 0.1 and heel[2] > 0.1:
                diffs.append(toe[0] - heel[0])
        if not diffs:
            return 1
        avg = sum(diffs) / len(diffs)
        return 1 if avg >= 0 else -1

    # --- accessors --------------------------------------------------------
    def idx(self, name: str) -> int:
        return self.keypoint_names.index(name)

    def pt(self, f: int, name: str) -> Point:
        return self.frames[f][self.idx(name)]

    def xy(self, f: int, name: str) -> XY:
        p = self.frames[f][self.idx(name)]
        if p[2] < self.analysis_min_confidence:
            return (float("nan"), float("nan"))
        return (p[0], p[1])

    def has(self, name: str) -> bool:
        return name in self.keypoint_names

    def series_xy(self, name: str) -> List[XY]:
        i = self.idx(name)
        return [(fr[i][0], fr[i][1]) for fr in self.frames]

    def series_y(self, name: str) -> List[float]:
        return [self.xy(f, name)[1] for f in range(self.n)]

    def series_x(self, name: str) -> List[float]:
        return [self.xy(f, name)[0] for f in range(self.n)]

    def filtered_for_analysis(
        self, min_confidence: float = 0.35, max_gap_seconds: float = 0.05
    ) -> "PoseSequence":
        """Return an analysis-only copy with short low-confidence gaps interpolated.

        A gap is filled only when trustworthy observations exist on both sides and
        its elapsed duration is no greater than ``max_gap_seconds``. Longer gaps
        keep their detector coordinates for the overlay but ``xy`` exposes them as
        NaN to metric calculations through ``analysis_min_confidence``.
        """
        frames = [[tuple(p) for p in fr] for fr in self.frames]
        for ki in range(len(self.keypoint_names)):
            i = 0
            while i < self.n:
                if frames[i][ki][2] >= min_confidence:
                    i += 1
                    continue
                start = i
                while i < self.n and frames[i][ki][2] < min_confidence:
                    i += 1
                end = i
                if start == 0 or end >= self.n:
                    continue
                # Measure the whole unobserved interval between trustworthy
                # endpoints. This stays correct for variable-frame-rate input.
                if self.elapsed(start - 1, end) > max_gap_seconds + 1e-9:
                    continue
                left, right = frames[start - 1][ki], frames[end][ki]
                if left[2] < min_confidence or right[2] < min_confidence:
                    continue
                for f in range(start, end):
                    alpha = (f - (start - 1)) / (end - (start - 1))
                    x = left[0] + alpha * (right[0] - left[0])
                    y = left[1] + alpha * (right[1] - left[1])
                    # Interpolation restores geometric continuity, not detector
                    # certainty. Keep it just usable while ensuring downstream
                    # tracking confidence cannot mistake it for an observation.
                    frames[f][ki] = (x, y, min_confidence)

        return replace(
            self,
            frames=frames,
            analysis_min_confidence=min_confidence,
        )

    # --- (de)serialization ------------------------------------------------
    def to_pose_dict(self) -> dict:
        d = {
            "schema": SCHEMA_VERSION,
            "source": self.source,
            "view": self.view,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "keypoint_names": self.keypoint_names,
            "frames": [[[round(v, 3) for v in p] for p in fr] for fr in self.frames],
        }
        if self.timestamps is not None:
            d["timestamps"] = [round(t, 4) for t in self.timestamps]
        return d

    @staticmethod
    def from_pose_dict(d: dict) -> "PoseSequence":
        frames = [
            [
                (float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 1.0)
                for p in fr
            ]
            for fr in d["frames"]
        ]
        ts = d.get("timestamps")
        return PoseSequence(
            fps=float(d.get("fps", 30.0)),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
            view=d.get("view", "side-left"),
            frames=frames,
            source=d.get("source", "unknown"),
            keypoint_names=list(d.get("keypoint_names", KEYPOINTS)),
            timestamps=[float(t) for t in ts] if ts is not None else None,
        )
