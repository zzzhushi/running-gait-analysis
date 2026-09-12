"""Descriptive lateral trunk sway per stride in a rear view."""

from __future__ import annotations

from ..ctx import per_stride_range
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    strikes = sorted(ctx.ev.strikes["l"] + ctx.ev.strikes["r"])[::2]
    return per_stride_range(ctx.neck_x_series(), strikes) / ctx.leg * 100.0


register(MetricDef(
    key=MetricKey.LATERAL_TRUNK_SWAY,
    label="Lateral trunk sway",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="Per-stride lateral neck motion relative to the pelvis; rear-view descriptive proxy.",
    confidence="low",
    evidence_level="screening",
    reference_ids=("Hensley2022", "Leporace2023"),
    views=("rear",),
    scored=False,
    compute=_compute,
    keypoints=("neck", "mid_hip"),
    requires_events=True,
))
