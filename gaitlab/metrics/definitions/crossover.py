"""Exploratory successive-foot crossover indicator, rear view."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    _width, crossover = ctx.step_width_and_crossover()
    return crossover


register(MetricDef(
    key=MetricKey.CROSSOVER,
    label="Crossover gait",
    unit="",
    good=(None, None),
    warn=(None, None),
    note="Whether at least two successive contralateral placement pairs reverse anatomical left/right order by more than the noise margin.",
    confidence="low",
    evidence_level="experimental",
    views=("rear",),
    scored=False,
    is_boolean=True,
    compute=_compute,
    keypoints=("l_hip", "r_hip", "l_ankle", "r_ankle"),
    event_phase="strike",
    card_visibility="always",
))
