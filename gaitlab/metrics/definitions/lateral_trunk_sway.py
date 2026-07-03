"""Lateral trunk sway — side-to-side upper-body sway per stride, rear view.

Custom trigger: a fixed 9%leg cutoff (not derived from the good/warn band) —
a deliberate, coarser threshold than the scoring band, not a bug.
"""

from __future__ import annotations

from ...core import geometry as geo
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    return geo.peak_to_peak(ctx.neck_x_series()) / ctx.leg * 100.0


def _trigger(defn, value, values, targets):
    if value != value or value <= 9:
        return None
    return "high", "low"


register(MetricDef(
    key=MetricKey.LATERAL_TRUNK_SWAY,
    label="Lateral trunk sway",
    unit="%leg",
    good=(None, 8),
    warn=(None, 12),
    note="Side-to-side lean of the upper body. A lot of sway often follows hip drop or a weak core.",
    confidence="high",
    views=("rear",),
    scored=True,
    compute=_compute,
    keypoints=("neck", "mid_hip"),
    trigger_fn=_trigger,
    finding_text={
        "high": {
            "title": "Trunk swaying side to side",
            "detail": (
                "Your upper body sways ~{value:.0f}% of a leg-length laterally each stride, often "
                "a knock-on of hip-drop or a weak core."
            ),
            "cue": "Keep the chest steady and square to the front.",
            "drill": "Anti-rotation core work (Pallof press) + the hip drills above.",
        },
    },
    exercises=[
        {"name": "Pallof press",
         "why": "Anti-rotation core to steady the trunk.",
         "dose": "3×10/side",
         "progression": "Split-stance / half-kneeling."},
        {"name": "Side planks",
         "why": "Lateral stability feeding into the hips.",
         "dose": "3×30s/side",
         "progression": "Add reaches."},
    ],
))
