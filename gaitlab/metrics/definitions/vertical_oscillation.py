"""Vertical oscillation — hip bounce per stride, side view, normalized by leg length."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    return ctx.vertical_oscillation_px() / ctx.leg * 100.0


def _trigger(defn, value, values, targets):
    t = targets.get(defn.key, defn)
    if t.status(value) != "bad":
        return None
    return "high", "low"


register(MetricDef(
    key=MetricKey.VERTICAL_OSCILLATION,
    label="Vertical oscillation",
    unit="%leg",
    good=(None, 12),
    warn=(None, 18),
    note="Bouncing wastes energy. Lower vertical travel of the hips is generally more economical.",
    confidence="high",
    views=("side",),
    scored=True,
    compute=_compute,
    keypoints=("mid_hip",),
    trigger_fn=_trigger,
    finding_text={
        "high": {
            "title": "You're bouncing",
            "detail": (
                "Your hips travel up and down ~{value:.0f}% of a leg-length each stride. Vertical "
                "bounce is energy spent fighting gravity instead of moving you forward."
            ),
            "cue": "Drive forward, not up — keep the crown of your head on a level line.",
            "drill": "Run tall past a fence/rail and keep your head height steady.",
        },
    },
    exercises=[
        {"name": "Run-tall-past-a-rail",
         "why": "Keeps energy going forward, not up.",
         "dose": "4×20s keeping head height level",
         "progression": "Combine with higher cadence."},
        {"name": "Pogo hops",
         "why": "Trains stiff, low, springy contacts.",
         "dose": "3×10",
         "progression": "Single-leg pogos."},
    ],
))
