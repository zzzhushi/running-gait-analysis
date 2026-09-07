"""Low-confidence rearfoot alignment proxy at estimated contact."""

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
    label="Rearfoot alignment at contact",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note=(
        "Image-plane heel-to-ankle alignment at estimated contact. It is not a measure of dynamic "
        "pronation and is reported only as a low-confidence screening observation."
    ),
    confidence="low",
    evidence_level="screening",
    reference_ids=("Hensley2022", "Leporace2023"),
    event_phase="strike",
    views=("rear",),
    scored=False,
    per_side=True,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high_abs",
    keypoints=("l_heel", "l_ankle", "r_heel", "r_ankle"),
    foi="max_pelvic_drop",
    card_per_side_key="pronation",
    value_confidence_fn=lambda value: "low",
))
