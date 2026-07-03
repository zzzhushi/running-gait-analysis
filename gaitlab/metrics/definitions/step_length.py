"""Step length — treadmill speed x step time (opposite-foot-to-foot), both views."""

from __future__ import annotations

from ..ctx import med, step_times
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    if not ctx.cal["speed_mps"]:
        return None
    steps = step_times(ctx.ev, side, ctx.seq.fps)
    if not steps:
        return None
    return ctx.cal["speed_mps"] * med(steps)


register(MetricDef(
    key=MetricKey.STEP_LENGTH,
    label="Step length",
    unit="m",
    good=(None, None),
    warn=(None, None),
    note="Distance per step (speed × step time).",
    confidence="moderate",
    views=("side", "rear"),
    scored=False,
    per_side=True,
    asym_direction="higher_better",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    card_visibility="conditional",
    card_per_side_key="step_length",
))
