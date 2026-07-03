"""Knee flexion — same smoothed per-side angle series, sampled at two different
gait events. Two metrics, one shared signal (see Ctx.knee_flexion_series), so
they live in one file rather than two.
"""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _midstance(ctx, side):
    kflex = ctx.knee_flexion_series(side)
    return med([kflex[m] for m in ctx.ev.midstance(side)])


def _contact(ctx, side):
    kflex = ctx.knee_flexion_series(side)
    return med([kflex[s] for s in ctx.ev.strikes[side]])


register(MetricDef(
    key=MetricKey.KNEE_FLEXION_MIDSTANCE,
    label="Knee flexion (midstance)",
    unit="deg",
    good=(38, 50),
    warn=(28, 58),
    note="~40-50 deg of knee bend at midstance absorbs landing shock. Stiff knees jar the joints.",
    confidence="high",
    views=("side",),
    scored=True,
    per_side=True,
    asym_direction="higher_better",
    compute=_midstance,
    per_side_compute=True,
    aggregate="worst_low",
    keypoints=("l_hip", "l_knee", "l_ankle", "r_hip", "r_knee", "r_ankle"),
    foi="l_midstance",
    card_per_side_key="knee_flexion_midstance",
    trigger_fn=lambda defn, value, values, targets: (
        ("any", "med") if targets.get(defn.key, defn).status(value) == "bad" else None
    ),
    finding_text={
        "any": {
            "title": "Stiff landing — let the knee bend",
            "detail": (
                "Your knee only bends ~{value:.0f} deg at midstance. A stiffer leg absorbs less "
                "shock, so more impact travels to the joints."
            ),
            "cue": "Aim for a soft, quiet landing — let the knee 'give' a little as you load it.",
            "drill": "Soft-landing drills and short downhill strides to train shock absorption.",
        },
    },
    exercises=[
        {"name": "Soft-landing drops",
         "why": "Teaches the knee to bend and absorb on landing.",
         "dose": "3×8 quiet landings",
         "progression": "Single-leg landings."},
        {"name": "Downhill strides",
         "why": "Forces shock absorption through the knee.",
         "dose": "4×20s on a gentle slope",
         "progression": "Slightly steeper / faster."},
    ],
))

register(MetricDef(
    key=MetricKey.KNEE_FLEXION_CONTACT,
    label="Knee flexion (contact)",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Knee bend angle at initial foot contact. Informational; more flex = softer landing.",
    confidence="high",
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_contact,
    per_side_compute=True,
    card_visibility="hidden",
))
