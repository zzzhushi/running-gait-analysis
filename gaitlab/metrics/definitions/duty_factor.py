"""Duty factor — share of the stride the foot is on the ground, side view."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    ct_s = ctx.ev.contact_time.get(side)
    stt = ctx.ev.stride_time.get(side)
    if ct_s and stt and stt > 0:
        return ct_s / stt * 100.0
    return float("nan")


register(MetricDef(
    key=MetricKey.DUTY_FACTOR,
    label="Duty factor",
    unit="%",
    good=(None, 40),
    warn=(None, 48),
    note=("Approximate share of the stride spent on the ground. Descriptive until the "
          "video-only contact anchor is calibrated against a reference."),
    confidence="low",
    views=("side",),
    scored=False,
    compute=_compute,
    per_side_compute=True,
    aggregate="max",
    card_per_side_key="duty_factor",
    card_status="info",
    # The current contact anchor is provisional. Keep the measurement visible, but do
    # not turn it into coaching until it is criterion-calibrated.
    trigger_fn=lambda *a: None,
    finding_text={
        "high": {
            "title": "Long duty factor",
            "detail": (
                "Your foot is on the ground for ~{value:.0f}% of each stride. A shorter, springier "
                "contact tends to be faster and more economical."
            ),
            "cue": "Quicker, lighter contacts — think 'off the ground fast'.",
            "drill": "Pogo hops and short hill sprints for reactive strength.",
        },
    },
    exercises=[
        {"name": "Pogo hops",
         "why": "Reactive strength to shorten ground contact.",
         "dose": "3×10",
         "progression": "Single-leg / depth pogos."},
        {"name": "Short hill sprints",
         "why": "Power and a springier contact.",
         "dose": "6×10s steep hill, walk back",
         "progression": "Add reps over weeks."},
    ],
))
