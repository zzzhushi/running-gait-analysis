"""Ground contact time — same underlying event data (ev.contact_time), exposed
as two keys: CONTACT_TIME (the always-shown descriptive headline) and
CONTACT_TIME_MS (the hidden per-side twin that feeds the headline card's L/R
display). One shared compute function, one file.

The current ankle-lift anchor is not criterion-calibrated, so these values remain visible
but are deliberately excluded from scoring, coaching, and asymmetry interpretation.
"""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    if side not in ctx.ev.contact_time:
        return float("nan")
    return ctx.ev.contact_time[side] * 1000.0


register(MetricDef(
    key=MetricKey.CONTACT_TIME,
    label="Ground contact time",
    unit="ms",
    good=(None, 250),
    warn=(None, 300),
    note=("Approximate time on the ground per step. The current video-only contact anchor "
          "has not yet been calibrated against high-speed video or a force reference."),
    confidence="low",
    views=("side",),
    scored=False,
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high",
    card_per_side_key="contact_time_ms",
    card_status="info",
    trigger_fn=lambda *a: None,
    finding_text={
        "high": {
            "title": "Long ground contact",
            "detail": (
                "You're spending ~{value:.0f} ms on the ground per step. Quicker, springier contacts "
                "tend to be more economical."
            ),
            "cue": "Think 'hot pavement' — get off the ground a little faster.",
            "drill": "Pogo hops and ankle-stiffness skips, 3×10, twice a week.",
        },
    },
    exercises=[
        {"name": "Ankle-stiffness skips",
         "why": "Shortens time on the ground.",
         "dose": "3×20m",
         "progression": "Faster turnover, same height."},
        {"name": "Pogo hops",
         "why": "Reactive strength for quicker contacts.",
         "dose": "3×10",
         "progression": "Add single-leg / depth pogos."},
    ],
))

register(MetricDef(
    key=MetricKey.CONTACT_TIME_MS,
    label="Ground contact time",
    unit="ms",
    good=(None, 250),
    warn=(None, 300),
    note="Approximate per-side contact time; descriptive until the event anchor is calibrated.",
    confidence="low",
    views=("side",),
    scored=False,
    per_side=False,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    card_visibility="hidden",
))
