"""Head lateral sway — side-to-side head movement per stride, rear view.
Only available when the pose source tracks a head keypoint."""

from __future__ import annotations

from ...core import geometry as geo
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    head_x = ctx.head_x_series()
    if head_x is None:
        return None
    return geo.peak_to_peak(head_x) / ctx.leg * 100.0


register(MetricDef(
    key=MetricKey.HEAD_LATERAL_SWAY,
    label="Head lateral sway",
    unit="%leg",
    good=(None, 6),
    warn=(None, 10),
    note="Side-to-side head movement per stride (rear view). Excess sway signals poor upper-body stability.",
    confidence="moderate",
    views=("rear",),
    scored=False,
    compute=_compute,
    card_visibility="conditional",
    finding_text={
        "high": {
            "title": "Head swaying side to side",
            "detail": (
                "Your head moves ~{value:.1f}% of a leg-length laterally per stride. "
                "Excess head sway wastes energy and can strain the neck and upper back."
            ),
            "cue": "Fix your gaze on a distant point and keep your head still over your shoulders as you run.",
            "drill": "Head-still drill: run and hold your eye level steady for 30 s. Pair with lateral hip work.",
        },
    },
))
