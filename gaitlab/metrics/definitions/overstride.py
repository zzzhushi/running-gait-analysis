"""Overstride — how far ahead of the hip the foot lands at contact, side view."""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    vals = []
    for s in ctx.ev.strikes[side]:
        ankle = ctx.seq.xy(s, f"{side}_ankle")
        hip = ctx.seq.xy(s, f"{side}_hip")
        vals.append(((ankle[0] - hip[0]) * ctx.facing) / ctx.leg * 100.0)
    return med(vals)


register(MetricDef(
    key=MetricKey.OVERSTRIDE,
    label="Forward foot placement at contact",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="Sagittal ankle position relative to the same-side hip at estimated contact, normalized to leg length; this is not center of mass, braking force, or an injury threshold.",
    confidence="low",
    evidence_level="experimental",
    reference_ids=("Hensley2022",),
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high",
    keypoints=("l_hip", "l_ankle", "r_hip", "r_ankle"),
    event_phase="strike",
    foi="l_strike",
    card_per_side_key="overstride",
))
