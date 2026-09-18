"""Flight time — time both feet are simultaneously off the ground, side view."""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    """Median airborne gap between stance intervals, measured directly rather than
    derived from cadence and mean contact time -- both of those are independently
    uncalibrated (see contact_time's own module), so deriving one from the other
    would compound their error instead of measuring anything new.

    Merges both feet's (start, end) stance intervals in start order (a classic
    interval-merge) so overlapping double-support does not register as a gap, using
    the same start/end-inclusive convention contact_time itself measures against.
    """
    intervals = sorted(iv for side_stances in ctx.ev.stance.values() for iv in side_stances)
    if len(intervals) < 2:
        return float("nan")
    gaps = []
    current_end = intervals[0][1]
    for s, to in intervals[1:]:
        if s > current_end:
            gaps.append(ctx.seq.elapsed(current_end, s) * 1000.0)
        current_end = max(current_end, to)
    return med(gaps)


register(MetricDef(
    key=MetricKey.FLIGHT_TIME,
    label="Flight time",
    unit="ms",
    good=(None, None),
    warn=(None, None),
    note="Time both feet are off the ground per step.",
    confidence="moderate",
    views=("side",),
    scored=False,
    compute=_compute,
    card_status="info",
))
