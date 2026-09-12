"""Vertical oscillation — hip bounce per stride, side view, normalized by leg length."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    return ctx.vertical_oscillation_px() / ctx.leg * 100.0


register(MetricDef(
    key=MetricKey.VERTICAL_OSCILLATION,
    label="Vertical oscillation",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="Per-stride mid-hip vertical image displacement normalized to leg length; descriptive only.",
    confidence="moderate",
    evidence_level="screening",
    reference_ids=("Malisoux2023",),
    views=("side",),
    scored=False,
    compute=_compute,
    keypoints=("mid_hip",),
    requires_events=True,
))
