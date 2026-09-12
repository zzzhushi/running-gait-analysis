"""Successive contralateral foot-placement width in a rear view."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    width, _crossover = ctx.step_width_and_crossover()
    return width


register(MetricDef(
    key=MetricKey.STEP_WIDTH,
    label="Successive foot-placement width",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="Rear-view distance between successive contralateral ankle placements in fixed-camera coordinates, normalized to leg length.",
    confidence="low",
    evidence_level="experimental",
    reference_ids=("Hensley2022", "Leporace2023"),
    views=("rear",),
    scored=False,
    compute=_compute,
    keypoints=("l_hip", "r_hip", "l_ankle", "r_ankle"),
    event_phase="strike",
))
