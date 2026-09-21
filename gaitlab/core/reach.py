"""Per-frame hip-relative foot position ("reach"): the signal overstride samples.

A wrong overstride value can come from a bad frame, a bad landmark, or a bad formula, and
without this signal materialized those three are indistinguishable -- the per-strike formula
computes a value and discards everything that produced it. This module exposes the whole
curve so a value can be traced back to its frame, its landmarks, and their confidences.

It is independent of contact detection: it maps every frame to a reach sample regardless of
whether that frame is a strike, so it can be tested and inspected without any event-detection
or annotation work. The denominator is a parameter, not a policy this module chooses --
see docs/metrics/overstride.md for why that choice is still open.

Ankle is the measurement point that reach_pct/inclination use, matching the metric's current
definition. Heel, toe, and their midpoint are exposed alongside it for comparison, not as
alternative definitions of overstride -- see docs/metrics/overstride.md's "Open decisions".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import geometry as geo
from .schema import PoseSequence, Point, XY

NAN = float("nan")


@dataclass(frozen=True)
class ReachSample:
    """One frame's hip-relative foot position, for one side.

    `foot_midpoint_proxy` is a derived point, not a tracked keypoint -- there is no midfoot
    landmark in the canonical schema. `denominator_px` is repeated on every sample rather than
    stored once because a future per-frame denominator (docs/metrics/overstride.md) should not
    require a different record shape.
    """

    frame: int
    t: float
    hip: Point
    ankle: Point
    heel: Point
    toe: Point
    foot_midpoint_proxy: XY
    facing: int
    denominator_px: float

    ankle_reach_px: float
    heel_reach_px: float
    toe_reach_px: float
    midpoint_reach_px: float

    ankle_reach_pct: float
    heel_reach_pct: float
    toe_reach_pct: float
    midpoint_reach_pct: float

    inclination_deg: float

    valid: bool
    invalid_reason: Optional[str]


def _signed_reach(x: float, hip_x: float, facing: int) -> float:
    return (x - hip_x) * facing


def _pct(reach_px: float, denominator_px: float) -> float:
    if reach_px != reach_px or denominator_px != denominator_px or denominator_px <= 0:
        return NAN
    return reach_px / denominator_px * 100.0


def reach_curve(seq: PoseSequence, side: str, denominator_px: float, facing: int) -> List[ReachSample]:
    """The hip-relative reach curve for one side, one sample per frame.

    `denominator_px` and `facing` are supplied rather than derived here, so this stays testable
    against a hand-computed denominator and usable once the denominator decision changes.
    """
    has_heel = seq.has(f"{side}_heel")
    has_toe = seq.has(f"{side}_big_toe")
    denom_ok = denominator_px == denominator_px and denominator_px > 0

    out: List[ReachSample] = []
    for f in range(seq.n):
        hip = seq.pt(f, f"{side}_hip")
        ankle = seq.pt(f, f"{side}_ankle")
        heel = seq.pt(f, f"{side}_heel") if has_heel else (0.0, 0.0, 0.0)
        toe = seq.pt(f, f"{side}_big_toe") if has_toe else (0.0, 0.0, 0.0)

        landmarks_ok = hip[2] > 0 and ankle[2] > 0
        if not landmarks_ok:
            reason = "hip or ankle not tracked this frame"
        elif not denom_ok:
            reason = "denominator unavailable (NaN or non-positive)"
        else:
            reason = None
        valid = reason is None

        if not landmarks_ok:
            out.append(ReachSample(
                frame=f, t=seq.time_at(f), hip=hip, ankle=ankle, heel=heel, toe=toe,
                foot_midpoint_proxy=(NAN, NAN), facing=facing, denominator_px=denominator_px,
                ankle_reach_px=NAN, heel_reach_px=NAN, toe_reach_px=NAN, midpoint_reach_px=NAN,
                ankle_reach_pct=NAN, heel_reach_pct=NAN, toe_reach_pct=NAN, midpoint_reach_pct=NAN,
                inclination_deg=NAN, valid=False, invalid_reason=reason,
            ))
            continue

        ankle_reach_px = _signed_reach(ankle[0], hip[0], facing)
        heel_reach_px = _signed_reach(heel[0], hip[0], facing) if heel[2] > 0 else NAN
        toe_reach_px = _signed_reach(toe[0], hip[0], facing) if toe[2] > 0 else NAN

        if heel[2] > 0 and toe[2] > 0:
            midpoint_xy = geo.midpoint(heel[:2], toe[:2])
            midpoint_reach_px = _signed_reach(midpoint_xy[0], hip[0], facing)
        else:
            midpoint_xy = (NAN, NAN)
            midpoint_reach_px = NAN

        inclination_deg = math.degrees(math.atan2(ankle_reach_px, ankle[1] - hip[1]))

        out.append(ReachSample(
            frame=f, t=seq.time_at(f), hip=hip, ankle=ankle, heel=heel, toe=toe,
            foot_midpoint_proxy=midpoint_xy, facing=facing, denominator_px=denominator_px,
            ankle_reach_px=ankle_reach_px, heel_reach_px=heel_reach_px,
            toe_reach_px=toe_reach_px, midpoint_reach_px=midpoint_reach_px,
            ankle_reach_pct=_pct(ankle_reach_px, denominator_px),
            heel_reach_pct=_pct(heel_reach_px, denominator_px),
            toe_reach_pct=_pct(toe_reach_px, denominator_px),
            midpoint_reach_pct=_pct(midpoint_reach_px, denominator_px),
            inclination_deg=inclination_deg, valid=valid, invalid_reason=reason,
        ))
    return out
