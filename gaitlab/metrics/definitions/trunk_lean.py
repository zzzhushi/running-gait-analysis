"""Descriptive trunk-segment lean from image vertical, side view only."""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    return med(ctx.trunk_lean_series())


register(MetricDef(
    key=MetricKey.TRUNK_LEAN,
    label="Trunk lean",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Sagittal mid-hip-to-neck segment angle relative to image vertical; interpret by speed and protocol.",
    confidence="moderate",
    evidence_level="screening",
    reference_ids=("Hensley2022", "Leporace2023"),
    views=("side",),
    scored=False,
    compute=_compute,
    keypoints=("mid_hip", "neck"),
))
