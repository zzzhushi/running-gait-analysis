"""Arm crossover — hands swinging across the body midline, rear view (boolean)."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    cross = sum(1 for f in range(ctx.n)
                if (ctx.seq.xy(f, "l_wrist")[0] - ctx.seq.xy(f, "mid_hip")[0]) > 0
                or (ctx.seq.xy(f, "r_wrist")[0] - ctx.seq.xy(f, "mid_hip")[0]) < 0)
    return cross > ctx.n * 0.25


def _trigger(defn, value, values, targets):
    return ("any", "low") if value else None


register(MetricDef(
    key=MetricKey.ARM_CROSSOVER,
    label="Arm crossover",
    unit="",
    good=(None, None),
    warn=(None, None),
    note="Arms swinging across the body midline add rotation that the trunk has to cancel out.",
    confidence="moderate",
    views=("rear",),
    scored=False,
    is_boolean=True,
    compute=_compute,
    trigger_fn=_trigger,
    card_visibility="hidden",
    finding_text={
        "any": {
            "title": "Arms crossing your midline",
            "detail": (
                "Your hands swing across the centre-line of your body. Cross-body arm swing drives "
                "a little rotation that your trunk and hips then have to cancel out."
            ),
            "cue": "Swing the arms front-to-back like pistons; thumbs graze the hips.",
            "drill": "Mirror arm-swing drill — keep the hands from crossing your zipper line.",
        },
    },
    exercises=[
        {"name": "Mirror arm-swing drill",
         "why": "Stops cross-body swing that adds rotation.",
         "dose": "3×20s, hands not crossing the midline",
         "progression": "Carry the cue into runs."},
    ],
))
