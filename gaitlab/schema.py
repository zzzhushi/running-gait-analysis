"""Normalized pose schema shared by every pose source (RTMPose, MediaPipe, synthetic).

Image coordinate convention: origin is the TOP-LEFT, +x points right, +y points DOWN.
So a point that is physically *higher off the ground* has a *smaller* y. Every helper
that reasons about height accounts for this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

SCHEMA_VERSION = "gaitlab.pose/v1"

# Canonical keypoint set: a superset that RTMPose-Halpe26 (26 kpts incl. 6 foot points)
# and MediaPipe-BlazePose (33 kpts) both map into. Order is fixed; arrays are aligned to it.
KEYPOINTS: List[str] = [
    "nose", "neck", "mid_hip",
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

    # --- basic info -------------------------------------------------------
    @property
    def n(self) -> int:
        return len(self.frames)

    @property
    def duration(self) -> float:
        return self.n / self.fps if self.fps else 0.0

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
        return (p[0], p[1])

    def has(self, name: str) -> bool:
        return name in self.keypoint_names

    def series_xy(self, name: str) -> List[XY]:
        i = self.idx(name)
        return [(fr[i][0], fr[i][1]) for fr in self.frames]

    def series_y(self, name: str) -> List[float]:
        i = self.idx(name)
        return [fr[i][1] for fr in self.frames]

    def series_x(self, name: str) -> List[float]:
        i = self.idx(name)
        return [fr[i][0] for fr in self.frames]

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
            timestamps=[float(t) for t in ts] if ts else None,
        )
