"""Knee drive (peak) — how far the thigh swings forward in swing/recovery.

Shares the raw thigh-lean series with hip_extension (Ctx.thigh_lean_series);
see that module for why.
"""

from __future__ import annotations

from ..ctx import per_stride_max
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    return per_stride_max(ctx.thigh_lean_series(side), ctx.ev.strikes[side])


register(MetricDef(
    key=MetricKey.KNEE_DRIVE,
    label="Knee drive (peak)",
    unit="deg",
    good=(20, None),
    warn=(10, None),
    note="How far the thigh swings forward in recovery. More knee drive feeds a longer, springier stride.",
    higher_is_better=True,
    confidence="high",
    views=("side",),
    scored=True,
    per_side=True,
    asym_direction="higher_better",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_low",
    keypoints=("l_hip", "l_knee", "r_hip", "r_knee"),
    card_per_side_key="knee_drive",
    finding_text={
        "low": {
            "title": "Limited knee drive",
            "detail": (
                "Your thigh swings forward only ~{value:.0f}° in recovery. More knee drive sets up "
                "a longer, springier stride and helps you hold pace."
            ),
            "cue": "Drive the knee forward and up a touch as the foot leaves the ground.",
            "drill": "A-skips and high-knee marching, building to bounding.",
        },
    },
    exercises=[
        {"name": "A-skips",
         "why": "Grooves an active forward-up knee drive.",
         "dose": "3×20m",
         "progression": "A-skips → bounding."},
        {"name": "High-knee marching",
         "why": "Strength and pattern for the knee lift.",
         "dose": "3×20m",
         "progression": "Add a run-out at the end."},
    ],
))
