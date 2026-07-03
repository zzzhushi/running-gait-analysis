"""Pelvic drop — how far the pelvis tilts toward the swinging leg at midstance,
rear view.

Custom value confidence: pose places a hip-line angle within a few degrees of
error, so small readings near that noise floor are downgraded. Custom
personalization: the good/warn band widens slightly for female runners (wider
pelvis / larger Q-angle).
"""

from __future__ import annotations

from dataclasses import replace

from ..ctx import med
from ..keys import MetricKey
from ..spec import NOISE_FLOOR_DEG, MetricDef, register


def _compute(ctx, side):
    tilt = ctx.pelvic_tilt_series()
    mids = ctx.ev.midstance(side)
    drops = [abs(tilt[m]) for m in mids] if mids else [abs(t) for t in tilt]
    return med(drops)


def _trigger(defn, value, values, targets):
    if value != value:
        return None
    t = targets.get(defn.key, defn)
    st = t.status(value)
    if st == "good":
        return None
    return "high", ("high" if st == "bad" else "med")


def _value_confidence(value):
    a = abs(value)
    if a < NOISE_FLOOR_DEG:
        return "low"
    return "moderate" if a <= 6.0 else "high"


def _personalize(defn, profile):
    if (profile.get("sex") or "").lower() != "female":
        return defn
    return replace(defn, good=(None, 7), warn=(None, 11),
                    note=defn.note + " (Range set for female norms, which typically show a little more pelvic motion.)")


register(MetricDef(
    key=MetricKey.PELVIC_DROP,
    label="Pelvic drop",
    unit="deg",
    good=(None, 6),
    warn=(None, 10),
    note="The hip of the swinging leg dropping >~10 deg points to weak hip stabilizers (injury risk).",
    confidence="moderate",  # value-dependent — see _value_confidence
    views=("rear",),
    scored=True,
    per_side=True,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high",
    keypoints=("l_hip", "r_hip"),
    foi="max_pelvic_drop",
    card_per_side_key="pelvic_drop",
    trigger_fn=_trigger,
    value_confidence_fn=_value_confidence,
    personalize_fn=_personalize,
    finding_text={
        "high": {
            "title": "Hip drop (weak stabilizers)",
            "detail": (
                "Your pelvis drops about {value:.0f} deg toward the swinging leg. Excess pelvic drop "
                "points to weak hip stabilizers and is linked to IT-band, knee, and hip pain."
            ),
            "cue": "Run 'level hips' — imagine balancing a cup of water on each hip.",
            "drill": "Hip strength: single-leg squats, side planks, banded hip-hikes, 3×/week.",
        },
    },
    exercises=[
        {"name": "Side planks",
         "why": "Builds lateral hip/core endurance to keep the pelvis level.",
         "dose": "3×30s/side",
         "progression": "Add top-leg raises."},
        {"name": "Banded hip-hikes",
         "why": "Directly trains the hip abductors that stop the drop.",
         "dose": "3×12/side",
         "progression": "Add load / standing on a step."},
        {"name": "Single-leg squats",
         "why": "Controls hip + knee under bodyweight on one leg.",
         "dose": "3×8/side",
         "progression": "Lower box / add weight."},
    ],
))
