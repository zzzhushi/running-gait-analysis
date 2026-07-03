"""Trunk lean — forward torso angle from vertical, side view only.

Custom trigger, same shape as cadence: the low side (too upright) flags on any
"warn" reading, but the high side (over-folding) only flags once fully "bad".
"""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, direction_of, register


def _compute(ctx, side=None):
    return med(ctx.trunk_lean_series())


def _trigger(defn, value, values, targets):
    if value != value:
        return None
    t = targets.get(defn.key, defn)
    st = t.status(value)
    lo, hi = t.good
    if st == "good" or not (value < lo or st == "bad"):
        return None
    sev = "high" if st == "bad" else "med"
    return direction_of(value, t.good), sev


register(MetricDef(
    key=MetricKey.TRUNK_LEAN,
    label="Trunk lean",
    unit="deg",
    good=(5, 12),
    warn=(0, 16),
    note="A slight forward lean from the ankles (~5-12 deg) helps. Upright = braking; too far = back load.",
    confidence="high",
    views=("side",),
    scored=True,
    compute=_compute,
    trigger_fn=_trigger,
    finding_text={
        "low": {
            "title": "Run a touch more forward",
            "detail": (
                "Your trunk is fairly upright ({value:.0f} deg). A small forward lean from the "
                "ankles helps you use gravity and reduces braking."
            ),
            "cue": "Think 'tall, then tip' — a gentle whole-body lean from the ankles.",
            "drill": "Falling-start drill: stand tall, lean until you have to step, repeat into a run.",
        },
        "high": {
            "title": "Too much trunk lean",
            "detail": (
                "You're leaning ~{value:.0f} deg forward, which can overload the lower back and "
                "hip flexors."
            ),
            "cue": "Lift the chest and run a little taller; lean from the ankles, not by folding at the waist.",
            "drill": "Wall posture drill + core anti-extension work (dead bugs, planks).",
        },
    },
    exercises=[
        {"name": "Lean-and-run drill",
         "why": "Finds a small whole-body forward lean.",
         "dose": "5×20m",
         "progression": "Hold the lean through a steady minute."},
        {"name": "Dead bugs / planks",
         "why": "A stable core lets you lean without folding.",
         "dose": "3×30s",
         "progression": "Add limb loading."},
    ],
))
