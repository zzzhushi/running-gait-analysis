"""Duty factor — share of the stride the foot is on the ground, side view."""

from __future__ import annotations

from ..keys import MetricKey
from ..reference_models import population_reference
from ..spec import MetricDef, register


def _compute(ctx, side):
    ct_s = ctx.ev.contact_time.get(side)
    stt = ctx.ev.stride_time.get(side)
    if ct_s and stt and stt > 0:
        return ct_s / stt * 100.0
    return float("nan")


register(MetricDef(
    key=MetricKey.DUTY_FACTOR,
    label="Duty factor",
    unit="%",
    good=(None, None),
    warn=(None, None),
    note="Observed contact time as a percentage of stride time. Compare only at matched running speed.",
    confidence="low",
    evidence_level="experimental",
    reference_ids=("Patoz2021", "Malisoux2023"),
    views=("side",),
    scored=False,
    compute=_compute,
    per_side_compute=True,
    aggregate="max",
    keypoints=("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="events",
    card_per_side_key="duty_factor",
    reference_fn=lambda profile: population_reference("duty_factor", profile),
))
