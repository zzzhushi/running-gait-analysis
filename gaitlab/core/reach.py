"""Per-frame hip-relative foot position ("reach"): the signal overstride samples.

A wrong overstride value can come from a bad frame, a bad landmark, or a bad formula, and
without this signal materialized those three are indistinguishable -- the per-strike formula
computes a value and discards everything that produced it. This module exposes the whole
curve so a value can be traced back to its frame, its landmarks, and their confidences.

It is independent of contact detection: it maps every frame to a reach sample regardless of
whether that frame is a strike, so it can be tested and inspected without any event-detection
or annotation work. The denominator is supplied, not chosen here -- see
docs/metrics/overstride.md for why that choice is still open.

Each distal candidate is computed from the landmarks it actually needs, and carries its own
unavailability reason. A candidate is not withheld because a different landmark is missing:
comparing candidates empirically is the reason they are all exposed, so an untracked ankle
must not erase heel, toe, or midpoint geometry. Availability in pixels and availability after
normalization are recorded separately, because a bad denominator leaves pixel offsets usable.

Ankle is the measurement point the metric currently uses. Heel, toe, and their midpoint are
exposed for comparison, not as alternative definitions -- see docs/metrics/overstride.md's
"Open decisions".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import geometry as geo
from .schema import Point, PoseSequence, XY

NAN = float("nan")


@dataclass(frozen=True)
class DenominatorSample:
    """One limb-length observation that fed the denominator, with its own traceability."""

    frame: int
    side: str
    thigh_px: float
    shank_px: float
    total_px: float
    min_confidence: float


@dataclass(frozen=True)
class Denominator:
    """The normalizing length, with enough provenance to audit a suspicious percentage.

    `samples` are the observations that produced `px`; they are empty when a caller injects a
    length directly rather than deriving it from the pose.
    """

    px: float
    method: str
    samples: Tuple[DenominatorSample, ...] = ()

    @classmethod
    def injected(cls, px: float, method: str = "injected") -> "Denominator":
        return cls(px=px, method=method)

    @property
    def unavailable(self) -> Optional[str]:
        if self.px != self.px:
            return "denominator is NaN"
        if self.px <= 0:
            return "denominator is not positive"
        return None


@dataclass(frozen=True)
class Reading:
    """One distal candidate's hip-relative offset.

    `px` and `pct` fail independently: missing landmarks make both unavailable, while a bad
    denominator leaves `px` usable and only invalidates `pct`.
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

    `foot_midpoint_proxy` is a derived point, not a tracked keypoint -- there is no midfoot
    landmark in the canonical schema. There is deliberately no sample-wide validity flag: a
    sample can hold a usable heel offset and an unusable ankle offset at once, so each
    measurement carries its own reason instead.
    """

    frame: int
    t: float
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
    """The hip-relative reach curve for one side, one sample per frame.

    `denominator` and `facing` are supplied rather than derived here, so this stays testable
    against a hand-computed length and usable once the denominator decision changes.
    """
    has_heel = seq.has(f"{side}_heel")
    has_toe = seq.has(f"{side}_big_toe")

    out: List[ReachSample] = []
    for f in range(seq.n):
        hip = seq.pt(f, f"{side}_hip")
        ankle = seq.pt(f, f"{side}_ankle")
        heel = seq.pt(f, f"{side}_heel") if has_heel else (0.0, 0.0, 0.0)
        toe = seq.pt(f, f"{side}_big_toe") if has_toe else (0.0, 0.0, 0.0)

        # The hip is the shared reference, so its absence is the only failure that takes
        # every candidate with it.
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
