"""Heel recovery — vertical heel pickup during swing (a springy-swing-leg proxy),
side view. Informational only."""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    heel_y = ctx.heel_y_series(side)
    strikes = ctx.ev.strikes[side]
    vals = []
    for i in range(len(strikes) - 1):
        seg = [v for v in heel_y[strikes[i]:strikes[i + 1]] if v == v]
        if len(seg) > 1:
            vals.append(max(seg) - min(seg))
    return (med(vals) / ctx.leg * 100.0) if vals else float("nan")


register(MetricDef(
    key=MetricKey.HEEL_RECOVERY,
    label="Heel recovery",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="How much the heel picks up in swing (proxy). More recovery = a shorter, springier swing leg.",
    confidence="moderate",
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    card_per_side_key="heel_recovery",
))
