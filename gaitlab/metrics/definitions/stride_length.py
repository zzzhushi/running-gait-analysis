"""Stride length — treadmill speed x stride time, both views (only available
when a treadmill speed is supplied for calibration)."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    if not ctx.cal["speed_mps"] or side not in ctx.ev.stride_time:
        return None
    return ctx.cal["speed_mps"] * ctx.ev.stride_time[side]


register(MetricDef(
    key=MetricKey.STRIDE_LENGTH,
    label="Stride length",
    unit="m",
    good=(None, None),
    warn=(None, None),
    note="From treadmill speed × stride time. Requires speed input.",
    confidence="moderate",
    views=("side", "rear"),
    scored=False,
    per_side=True,
    asym_direction="higher_better",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    card_visibility="conditional",
    card_per_side_key="stride_length",
))
