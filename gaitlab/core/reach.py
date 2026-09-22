"""Per-frame hip-relative foot position, the signal overstride samples.

Every frame yields a sample regardless of contact detection, so the quantity is inspectable
without event detection or annotation.

Each distal candidate is computed from the landmarks it needs alone; the hip is the shared
reference, so only its absence makes every candidate unavailable. Pixel and normalized
availability are separate, because an unusable denominator leaves pixel offsets measurable.

Ankle is the measurement point the metric uses; heel, toe and their midpoint are exposed for
comparison, not as alternative definitions. The denominator is supplied rather than chosen
here, and the measurement contract records why that choice is open.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import geometry as geo
from .schema import Point, PoseSequence, XY

NAN = float("nan")


@dataclass(frozen=True)
class DenominatorSample:
    """One limb-length observation behind the denominator.

    Retains the raw points, so the segment lengths can be recomputed from this record alone.
    """

    frame: int
    t: float
    side: str
    hip: Point
    knee: Point
    ankle: Point
    thigh_px: float
    shank_px: float
    total_px: float
    min_confidence: float


@dataclass(frozen=True)
class Denominator:
    """The normalizing length in pixels, with the observations that produced it.

    `samples` is empty when a caller injects a length rather than deriving it from pose.
    `unavailable` names why the length cannot normalize, or None.
    """

    px: float
    method: str
    samples: Tuple[DenominatorSample, ...] = ()
    source_unavailable: Optional[str] = None

    @classmethod
    def injected(cls, px: float, method: str = "injected") -> "Denominator":
        return cls(px=px, method=method)

    @property
    def unavailable(self) -> Optional[str]:
        if self.source_unavailable:
            return self.source_unavailable
        if self.px != self.px:
            return "denominator is NaN"
        if self.px <= 0:
            return "denominator is not positive"
        return None


@dataclass(frozen=True)
class Reading:
    """One distal candidate's hip-relative offset, in pixels and as a percentage.

    Missing landmarks make both unavailable; an unusable denominator invalidates `pct` only.
    """

    px: float
    pct: float
    px_unavailable: Optional[str]
    pct_unavailable: Optional[str]

    @property
    def available(self) -> bool:
        return self.pct_unavailable is None


@dataclass(frozen=True)
class ReachSample:
    """One frame's hip-relative foot position, for one side.

    `foot_midpoint_proxy` is derived, not a tracked keypoint: the schema has no midfoot
    landmark. Availability is per measurement, since one sample can hold a usable heel offset
    and an unusable ankle offset at once.
    """

    frame: int
    t: float
    side: str
    processing: str
    hip: Point
    ankle: Point
    heel: Point
    toe: Point
    foot_midpoint_proxy: XY
    facing: int
    denominator: Denominator

    ankle_reach: Reading
    heel_reach: Reading
    toe_reach: Reading
    midpoint_reach: Reading

    inclination_deg: float
    inclination_unavailable: Optional[str]


def _reading(distal_x: float, hip_x: float, facing: int, denominator: Denominator,
             missing: Optional[str]) -> Reading:
    if missing:
        return Reading(NAN, NAN, missing, missing)
    px = (distal_x - hip_x) * facing
    denom_missing = denominator.unavailable
    if denom_missing:
        return Reading(px, NAN, None, denom_missing)
    return Reading(px, px / denominator.px * 100.0, None, None)


def reach_curve(seq: PoseSequence, side: str, denominator: Denominator, facing: int) -> List[ReachSample]:
    """Return one sample per frame for `side`.

    `denominator` and `facing` are supplied, so the curve is independent of how either is
    derived.
    """
    has_heel = seq.has(f"{side}_heel")
    has_toe = seq.has(f"{side}_big_toe")

    out: List[ReachSample] = []
    for f in range(seq.n):
        hip = seq.pt(f, f"{side}_hip")
        ankle = seq.pt(f, f"{side}_ankle")
        heel = seq.pt(f, f"{side}_heel") if has_heel else (0.0, 0.0, 0.0)
        toe = seq.pt(f, f"{side}_big_toe") if has_toe else (0.0, 0.0, 0.0)

        no_hip = None if hip[2] > 0 else "hip not tracked this frame"
        no_ankle = no_hip or (None if ankle[2] > 0 else "ankle not tracked this frame")
        no_heel = no_hip or (None if heel[2] > 0 else "heel not tracked this frame")
        no_toe = no_hip or (None if toe[2] > 0 else "big toe not tracked this frame")
        no_midpoint = no_heel or no_toe

        if no_midpoint:
            midpoint_xy: XY = (NAN, NAN)
            midpoint_x = NAN
        else:
            midpoint_xy = geo.midpoint(heel[:2], toe[:2])
            midpoint_x = midpoint_xy[0]

        if no_ankle:
            inclination_deg = NAN
        else:
            inclination_deg = math.degrees(math.atan2((ankle[0] - hip[0]) * facing, ankle[1] - hip[1]))

        out.append(ReachSample(
            frame=f,
            t=seq.time_at(f),
            side=side,
            processing="raw",
            hip=hip, ankle=ankle, heel=heel, toe=toe,
            foot_midpoint_proxy=midpoint_xy,
            facing=facing,
            denominator=denominator,
            ankle_reach=_reading(ankle[0], hip[0], facing, denominator, no_ankle),
            heel_reach=_reading(heel[0], hip[0], facing, denominator, no_heel),
            toe_reach=_reading(toe[0], hip[0], facing, denominator, no_toe),
            midpoint_reach=_reading(midpoint_x, hip[0], facing, denominator, no_midpoint),
            inclination_deg=inclination_deg,
            inclination_unavailable=no_ankle,
        ))
    return out
