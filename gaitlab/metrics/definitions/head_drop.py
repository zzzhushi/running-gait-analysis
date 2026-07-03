"""Head bobbing — vertical head-crown bounce per stride, side view.

Only available when the pose source tracks a head keypoint. Custom trigger:
value-derived — compares against vertical_oscillation rather than a fixed band,
since the question is whether the head moves independently of the hips.
"""

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
    vals = [max(head_y[strikes[i]:strikes[i + 1]]) - min(head_y[strikes[i]:strikes[i + 1]])
            for i in range(len(strikes) - 1) if head_y[strikes[i]:strikes[i + 1]]]
    head_px = med(vals) if vals else geo.peak_to_peak(head_y)
    return head_px / ctx.leg * 100.0


def _trigger(defn, value, values, targets):
    vo = values.get(MetricKey.VERTICAL_OSCILLATION)
    if value != value or vo != vo or value <= max(vo * 1.5, 5.0):
        return None
    return "high", "low"


def _extra_fmt(values):
    return {"ref": values.get(MetricKey.VERTICAL_OSCILLATION)}


register(MetricDef(
    key=MetricKey.HEAD_DROP,
    label="Head bobbing",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note=(
        "Vertical head-crown bounce per stride. Ideally tracks with hip VO; "
        "a much higher value suggests the head is nodding independently."
    ),
    confidence="moderate",
    views=("side",),
    scored=False,
    compute=_compute,
    trigger_fn=_trigger,
    extra_fmt_fn=_extra_fmt,
    card_visibility="conditional",
    finding_text={
        "high": {
            "title": "Head bobbing",
            "detail": (
                "Your head bounces ~{value:.1f}% of a leg-length per stride — noticeably more than "
                "your hip ({ref:.1f}%). Extra head movement is wasted energy and can contribute to "
                "neck and upper-back fatigue."
            ),
            "cue": "Keep your chin level and fix your gaze on the horizon — imagine a book balanced on your head.",
            "drill": "Head-still drill: run alongside a fence and keep your eye level steady for 30 s at a time.",
        },
    },
))
