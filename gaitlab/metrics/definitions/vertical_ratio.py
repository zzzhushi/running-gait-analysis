"""Vertical ratio — bounce relative to step length; a calibration-gated economy
proxy (lower is more economical, ~6-7% is typical for efficient runners).
"""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    if not (ctx.cal["px_per_cm"] and ctx.cal["speed_mps"]):
        return None
    cadence = ctx.ev.cadence_spm
    if cadence != cadence or cadence <= 0:
        return None
    vo_cm = ctx.vertical_oscillation_px() / ctx.cal["px_per_cm"]
    step_time = 60.0 / cadence
    step_len_m = ctx.cal["speed_mps"] * step_time
    if step_len_m <= 0:
        return None
    return (vo_cm / 100.0) / step_len_m * 100.0


register(MetricDef(
    key=MetricKey.VERTICAL_RATIO,
    label="Vertical ratio",
    unit="%",
    good=(None, None),
    warn=(None, None),
    note="Bounce relative to step length — lower is more economical (~6-7% is good).",
    confidence="moderate",
    views=("side",),
    scored=False,
    compute=_compute,
    card_visibility="conditional",
))
