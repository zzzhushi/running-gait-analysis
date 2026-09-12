"""Head lateral sway — side-to-side head movement per stride, rear view.
Only available when the pose source tracks a head keypoint."""

from __future__ import annotations

from ..ctx import per_stride_range
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    head_x = ctx.head_x_series()
    if head_x is None:
        return None
    strikes = sorted(ctx.ev.strikes["l"] + ctx.ev.strikes["r"])[::2]
    return per_stride_range(head_x, strikes) / ctx.leg * 100.0


register(MetricDef(
    key=MetricKey.HEAD_LATERAL_SWAY,
    label="Head lateral sway",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="Per-stride lateral head motion relative to the pelvis; informational rear-view proxy.",
    confidence="low",
    evidence_level="experimental",
    views=("rear",),
    scored=False,
    compute=_compute,
    keypoints=("head", "mid_hip"),
    requires_events=True,
    card_visibility="conditional",
))
