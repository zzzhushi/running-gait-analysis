"""Cadence — steps per minute, from either view (comes straight off gait events).

Custom trigger: the low side flags on any "warn" reading, but the high side only
flags once it's fully "bad" (>195 stock, or the personalized equivalent) — a
brisk-but-not-pathological cadence in the upper-warn band is not worth a coaching
note. Custom personalization: the efficient band shifts with the runner's stature
and pace (shorter runners and faster paces sit higher than the old "180" rule).
"""

from __future__ import annotations

from dataclasses import replace

from ..keys import MetricKey
from ..spec import MetricDef, direction_of, register


def _compute(ctx, side=None):
    return ctx.ev.cadence_spm


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


def _personalize(defn, profile):
    height = profile.get("height_cm")
    leg = profile.get("leg_length_cm")
    speed = profile.get("speed_kmh")
    h = (leg / 0.48) if leg else height
    if not h:
        return defn
    center = 188.0 - 0.615 * (float(h) - 157.0)
    if speed:
        center += 1.2 * (float(speed) - 10.0)
    center = max(160.0, min(200.0, center))
    note = (
        f"Personalized to your stature{' and speed' if speed else ''}: you're likely most "
        f"efficient near {center:.0f} steps/min. Shorter runners and faster paces sit higher "
        "than the old '180' rule of thumb."
    )
    return replace(defn, good=(round(center - 7), round(center + 7)),
                   warn=(round(center - 14), round(center + 14)), note=note)


register(MetricDef(
    key=MetricKey.CADENCE,
    label="Cadence",
    unit="spm",
    good=(170, 185),
    warn=(160, 195),
    note="Most runners are efficient at 170-185 steps/min. Low cadence usually means overstriding.",
    higher_is_better=True,
    confidence="high",
    views=("side", "rear"),
    trigger_views=("side",),  # scored/carded in both views, but only coached in side view
    scored=True,
    compute=_compute,
    trigger_fn=_trigger,
    personalize_fn=_personalize,
    finding_text={
        "low": {
            "title": "Increase your cadence",
            "detail": (
                "Your cadence is about {value:.0f} steps/min. Most runners are more efficient at "
                "170-185. A low cadence usually goes hand-in-hand with overstriding and harder impacts."
            ),
            "cue": "Take quicker, lighter steps — aim to bump your step rate ~5-10% without speeding up.",
            "drill": "Run 4×30s to a metronome set at your target cadence; jog easy between.",
        },
        "high": {
            "title": "Your cadence is very high",
            "detail": (
                "Your cadence is about {value:.0f} steps/min, above the typical efficient range. An "
                "unusually high cadence can indicate overly short, shuffling steps and may limit "
                "stride power."
            ),
            "cue": "Allow a little more flight time — let each stride open up a touch.",
            "drill": "Relaxed strides at easy pace focusing on full hip extension at push-off.",
        },
    },
    exercises=[
        {"name": "Metronome strides",
         "why": "Trains a quicker, lighter turnover.",
         "dose": "4×30s at target cadence, easy jog between",
         "progression": "Hold the new cadence for whole easy runs."},
        {"name": "Quick-feet A-skips",
         "why": "Grooves fast ground contacts.",
         "dose": "3×20m, 2-3×/week",
         "progression": "Add B-skips, then build to strides."},
    ],
))
