"""Anthropometrically normalized spatial/speed outputs."""

from __future__ import annotations

import math

from ..ctx import med, step_times
from ..keys import MetricKey
from ..spec import MetricDef, register


def _step_leg_ratio(ctx, side):
    speed = ctx.cal["speed_mps"]
    px_per_cm = ctx.cal["px_per_cm"]
    if not speed or not px_per_cm:
        return None
    steps = step_times(ctx.ev, side, ctx.seq)
    leg_m = (ctx.leg / px_per_cm) / 100.0
    return speed * med(steps) / leg_m * 100.0 if steps and leg_m > 0 else None


def _dimensionless_speed(ctx, side=None):
    speed = ctx.cal["speed_mps"]
    px_per_cm = ctx.cal["px_per_cm"]
    if not speed or not px_per_cm:
        return None
    leg_m = (ctx.leg / px_per_cm) / 100.0
    return speed / math.sqrt(9.80665 * leg_m) if leg_m > 0 else None


register(MetricDef(
    key=MetricKey.STEP_LENGTH_LEG_RATIO, label="Step length / leg length", unit="%",
    good=(None, None), warn=(None, None),
    note="Speed × step time normalized to measured leg length; compare at matched dimensionless speed.",
    confidence="moderate", evidence_level="screening", views=("side", "rear"), scored=False,
    reference_ids=("Hof1996", "Malisoux2023"),
    per_side=True, compute=_step_leg_ratio, per_side_compute=True,
    keypoints=("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="events", card_per_side_key="step_length_leg_ratio", card_visibility="conditional",
))

register(MetricDef(
    key=MetricKey.DIMENSIONLESS_SPEED, label="Dimensionless speed", unit="",
    good=(None, None), warn=(None, None),
    note="Running speed / sqrt(g × leg length), which supports stature-aware comparisons.",
    confidence="moderate", evidence_level="screening", views=("side", "rear"), scored=False,
    reference_ids=("Hof1996",),
    compute=_dimensionless_speed, card_visibility="conditional",
    keypoints=("l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle"),
))
