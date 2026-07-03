"""Hip extension (peak) — how far the thigh drives behind vertical at push-off.

Shares the raw thigh-lean series with knee_drive (Ctx.thigh_lean_series); this
metric just reads the negative side (behind vertical) and knee_drive the
positive side (forward, in recovery).
"""

from __future__ import annotations

from ..ctx import per_stride_max
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    behind = [-v for v in ctx.thigh_lean_series(side)]
    return per_stride_max(behind, ctx.ev.strikes[side])


def _trigger(defn, value, values, targets):
    if value != value:
        return None
    t = targets.get(defn.key, defn)
    st = t.status(value)
    if st == "good":
        return None
    return "low", ("med" if st == "bad" else "low")


register(MetricDef(
    key=MetricKey.HIP_EXTENSION,
    label="Hip extension (peak)",
    unit="deg",
    good=(10, None),
    warn=(5, None),
    note=(
        "How far the thigh drives behind you at push-off. Limited extension often means tight hip "
        "flexors or under-active glutes — and a tendency to overstride to compensate."
    ),
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
    foi="l_toeoff",
    card_per_side_key="hip_extension",
    trigger_fn=_trigger,
    finding_text={
        "low": {
            "title": "Limited hip extension",
            "detail": (
                "Your thigh drives only about {value:.0f}° behind you at push-off. Limited hip "
                "extension usually traces to tight hip flexors or under-active glutes, and it nudges "
                "you toward reaching out in front for stride length (overstriding) instead."
            ),
            "cue": "Push the ground back behind you and stay tall through the hips.",
            "drill": "Hip-flexor mobility + glute activation: hip extensions, bridges, bounding strides.",
        },
    },
    exercises=[
        {"name": "Couch stretch (hip flexors)",
         "why": "Frees the front of the hip so the thigh can drive back.",
         "dose": "2×45s/side daily",
         "progression": "Add an active glute squeeze at end range."},
        {"name": "Glute bridges → single-leg",
         "why": "Wakes up the glutes for push-off.",
         "dose": "3×12, then 3×8/leg",
         "progression": "Hip thrusts with load."},
        {"name": "Bounding strides",
         "why": "Trains powerful hip extension at speed.",
         "dose": "4×20m, 1-2×/week",
         "progression": "Increase distance/height once smooth."},
    ],
))
