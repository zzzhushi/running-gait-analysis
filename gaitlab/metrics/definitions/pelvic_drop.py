"""Signed swing-side pelvic drop at estimated midstance, rear view."""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    tilt = ctx.pelvic_tilt_series()
    baseline = med(tilt)
    sign = 1.0 if side == "l" else -1.0
    return med([sign * (tilt[frame] - baseline) for frame in ctx.ev.midstance(side)])


register(MetricDef(
    key=MetricKey.PELVIC_DROP,
    label="Swing-side pelvic drop",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Signed swing-side drop relative to the clip median hip line; negative values indicate pelvic hike. Rear-view screening only.",
    confidence="low",
    evidence_level="screening",
    reference_ids=("Hensley2022", "Leporace2023"),
    views=("rear",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    keypoints=("l_hip", "r_hip"),
    event_phase="midstance",
    foi="max_pelvic_drop",
    card_per_side_key="pelvic_drop",
))
