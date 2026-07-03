"""Pronation (estimate) — rear-foot roll-in at contact, rear view.

Low-confidence 2-D estimate (a partly-occluded angle), so confidence is always
"low" regardless of magnitude, and it's excluded from the headline score. The
global (worst-side) value compares magnitudes (abs), while the per-side display
keeps the sign (direction of roll) — see `aggregate="worst_high_abs"`.
"""

from __future__ import annotations

import math

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    frames = ctx.ev.strikes[side] or ctx.ev.midstance(side) or list(range(0, ctx.n, max(1, ctx.n // 8)))
    vals = []
    for s in frames:
        ankle = ctx.seq.xy(s, f"{side}_ankle")
        heel = ctx.seq.xy(s, f"{side}_heel")
        mid = ctx.seq.xy(s, "mid_hip")[0]
        dx = ankle[0] - heel[0]
        dy = abs(ankle[1] - heel[1]) + 1e-6
        toward_mid = 1.0 if ankle[0] < mid else -1.0
        vals.append(math.degrees(math.atan2(dx * toward_mid, dy)))
    return med(vals)


register(MetricDef(
    key=MetricKey.PRONATION,
    label="Pronation (estimate)",
    unit="deg",
    good=(None, 8),
    warn=(None, 12),
    note=(
        "Estimated rear-foot roll-in at contact. This is a low-confidence 2-D rear-view estimate — "
        "treat it as a flag to check your shoe wear and ankle, not a measurement."
    ),
    confidence="low",
    views=("rear",),
    scored=False,  # low confidence, excluded from headline score
    per_side=True,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high_abs",
    keypoints=("l_heel", "l_ankle", "r_heel", "r_ankle"),
    foi="max_pelvic_drop",
    card_per_side_key="pronation",
    value_confidence_fn=lambda value: "low",
    finding_text={
        "high": {
            "title": "Possible overpronation (estimate)",
            "detail": (
                "The rear-foot appears to roll inward ~{value:.0f}° at contact. This is a "
                "low-confidence 2-D rear-view estimate, so treat it as a prompt to look closer "
                "rather than a verdict."
            ),
            "cue": "Check the wear pattern on your shoes; a stability shoe may help if it's pronounced.",
            "drill": "Calf and foot strength (heel raises, short-foot drills); review footwear with a fitter.",
        },
    },
    exercises=[
        {"name": "Heel raises",
         "why": "Calf/foot strength to control roll-in.",
         "dose": "3×15",
         "progression": "Single-leg, then off a step."},
        {"name": "Short-foot drill",
         "why": "Trains the arch muscles.",
         "dose": "3×10 holds/side",
         "progression": "Standing → single-leg balance."},
        {"name": "Check footwear",
         "why": "Worn or wrong-support shoes amplify roll-in.",
         "dose": "Review shoe wear; consider a fitting",
         "progression": "Trial a stability shoe if pronounced."},
    ],
))
