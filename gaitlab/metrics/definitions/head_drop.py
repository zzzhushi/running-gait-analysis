"""Descriptive vertical head-crown displacement per stride, side view."""

from __future__ import annotations

from ...core import geometry as geo
from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    head_y = ctx.head_y_series()
    if head_y is None:
        return None
    strikes = ctx.ev.strikes["l"]
    vals = []
    for start, end in zip(strikes, strikes[1:]):
        segment = [value for value in head_y[start:end] if value == value]
        if segment:
            vals.append(max(segment) - min(segment))
    head_px = med(vals) if vals else geo.peak_to_peak(head_y)
    return head_px / ctx.leg * 100.0


register(MetricDef(
    key=MetricKey.HEAD_DROP,
    label="Head bobbing",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note=(
        "Per-stride vertical head-crown image displacement normalized to leg length."
    ),
    confidence="low",
    evidence_level="experimental",
    views=("side",),
    scored=False,
    compute=_compute,
    keypoints=("head", "mid_hip"),
    requires_events=True,
    card_visibility="conditional",
))
