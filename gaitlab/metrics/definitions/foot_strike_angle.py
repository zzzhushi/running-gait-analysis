"""Foot-segment angle and categorical contact pattern, side view."""

from __future__ import annotations

import math

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    vals = []
    for s in ctx.ev.strikes[side]:
        heel = ctx.seq.xy(s, f"{side}_heel")
        toe = ctx.seq.xy(s, f"{side}_big_toe")
        dx = (toe[0] - heel[0]) * ctx.facing
        dy = toe[1] - heel[1]
        vals.append(math.degrees(math.atan2(-dy, abs(dx) + 1e-6)))
    return med(vals)


register(MetricDef(
    key=MetricKey.FOOT_STRIKE_ANGLE,
    label="Foot-strike angle",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note=(
        "Foot-segment angle to image horizontal at estimated contact. Classification uses published "
        "2-D thresholds, but a tilted camera or non-level ground biases the result."
    ),
    confidence="low",
    evidence_level="screening",
    reference_ids=("Altman2012", "Oliveira2019", "Hensley2022"),
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    keypoints=("l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="strike",
))
