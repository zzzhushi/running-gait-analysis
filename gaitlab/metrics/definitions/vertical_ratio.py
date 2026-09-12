"""Vertical image displacement relative to calibrated step length."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    if not (ctx.cal.px_per_cm and ctx.cal.speed_mps):
        return None
    cadence = ctx.ev.cadence_spm
    if cadence != cadence or cadence <= 0:
        return None
    vo_cm = ctx.vertical_oscillation_px() / ctx.cal.px_per_cm
    step_time = 60.0 / cadence
    step_len_m = ctx.cal.speed_mps * step_time
    if step_len_m <= 0:
        return None
    return (vo_cm / 100.0) / step_len_m * 100.0


register(MetricDef(
    key=MetricKey.VERTICAL_RATIO,
    label="Vertical ratio",
    unit="%",
    good=(None, None),
    warn=(None, None),
    note="Calibrated vertical image displacement divided by speed-derived step length; descriptive and protocol dependent.",
    confidence="low",
    evidence_level="experimental",
    views=("side",),
    scored=False,
    compute=_compute,
    keypoints=("mid_hip", "l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    requires_events=True,
    card_visibility="conditional",
))
