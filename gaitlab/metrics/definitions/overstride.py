"""Overstride — horizontal ankle-to-hip offset at initial contact, side view.

Positive means the foot lands ahead of the hip in the direction of travel; `ctx.facing`
supplies that direction so either side view reads the same sign. Divided by a projected
pose-leg length and reported as a percentage, then aggregated per side as a median across that
side's contacts. The unit is percent of that projected length, not of an anthropometric one.

Modeled after Lieberman et al. 2015's d_OH (J Exp Biol 218:3406), which associates this
distance with braking impulse. Not a reproduction of it: the landmarks are pose keypoint
proxies for the markers that work used, the denominator is projected rather than a standing
anthropometric length, and contact is a heuristic boundary rather than force-plate onset. The
good/warn bands come from neither source and carry no evidence. See
docs/metrics/overstride.md for the status of each constant.
"""

from __future__ import annotations

from ..ctx import median
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    vals = []
    for s in ctx.ev.strikes[side]:
        ankle = ctx.seq.xy(s, f"{side}_ankle")
        hip = ctx.seq.xy(s, f"{side}_hip")
        vals.append(((ankle[0] - hip[0]) * ctx.facing) / ctx.leg * 100.0)
    return median(vals)


def _trigger(defn, value, values, targets):
    if value != value:
        return None
    t = targets.get(defn.key, defn)
    st = t.status(value)
    if st == "good":
        return None
    return "high", ("high" if st == "bad" else "med")


register(MetricDef(
    key=MetricKey.OVERSTRIDE,
    label="Overstride",
    unit="%leg",
    # Heuristic bands: no published percent-of-leg-length cutoff for overstride was found.
    # TODO: add comment citing a threshold source, or stop scoring this metric.
    good=(None, 8),
    warn=(None, 15),
    note="Foot should land close to under your hips. Landing far ahead (>~8% of leg length) brakes you.",
    confidence="high",
    views=("side",),
    scored=True,
    per_side=True,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high",
    keypoints=("l_hip", "l_ankle", "r_hip", "r_ankle"),
    anchor_frame="l_strike",
    card_per_side_key="overstride",
    trigger_fn=_trigger,
    finding_text={
        "high": {
            "title": "You're overstriding",
            "detail": (
                "Your foot lands about {value:.0f}% of a leg-length ahead of your hips. Landing "
                "that far out in front creates a braking force on every step and raises impact loading."
            ),
            "cue": "Let your foot land closer to under your hips, and lean slightly from the ankles — not the waist.",
            "drill": "High-cadence strides: 6×20s focusing on quick feet landing beneath you.",
        },
    },
    exercises=[
        {"name": "High-cadence strides",
         "why": "Pulls the foot-strike back under your hips.",
         "dose": "6×20s focusing on landing beneath you",
         "progression": "Blend into tempo running."},
        {"name": "Falling-start runs",
         "why": "Teaches leaning from the ankles, not reaching.",
         "dose": "6×20m from a tall lean",
         "progression": "Carry the lean into a relaxed cruise."},
        {"name": "Wall posture drill",
         "why": "Builds the tall, forward-from-the-ankle position.",
         "dose": "3×30s holds",
         "progression": "Add a marching knee-drive."},
    ],
))
