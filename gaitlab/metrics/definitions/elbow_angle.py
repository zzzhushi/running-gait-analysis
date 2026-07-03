"""Elbow angle — relaxed arm-carry angle, side view.

Custom trigger: a fixed 110° cutoff (not derived from the good/warn band) —
this is a deliberate, coarser threshold than the scoring band, not a bug; it
predates the band-driven trigger style used elsewhere in this file.
"""

from __future__ import annotations

from ...core import geometry as geo
from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    return med([geo.angle_3pt(ctx.seq.xy(f, f"{side}_shoulder"), ctx.seq.xy(f, f"{side}_elbow"),
                               ctx.seq.xy(f, f"{side}_wrist"))
                for f in range(ctx.n)])


def _trigger(defn, value, values, targets):
    if value != value or value <= 110:
        return None
    return "high", "low"


register(MetricDef(
    key=MetricKey.ELBOW_ANGLE,
    label="Elbow angle",
    unit="deg",
    good=(75, 105),
    warn=(60, 120),
    note="A relaxed ~90° elbow. Very straight arms waste energy and tend to swing across the body.",
    confidence="high",
    views=("side",),
    scored=True,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    keypoints=("l_shoulder", "l_elbow", "l_wrist", "r_shoulder", "r_elbow", "r_wrist"),
    card_per_side_key="elbow_angle",
    trigger_fn=_trigger,
    finding_text={
        "high": {
            "title": "Relax and bend your arms",
            "detail": (
                "Your elbows are quite straight (~{value:.0f}°). Long, straight arms waste energy "
                "and tend to swing across your body."
            ),
            "cue": "Bend the elbows to about 90° and swing front-to-back, hands relaxed.",
            "drill": "Arm-swing drill: 3×20s driving the elbows back, not across.",
        },
    },
    exercises=[
        {"name": "Arm-swing drill",
         "why": "Trains a relaxed ~90° elbow swinging front-to-back.",
         "dose": "3×20s, tall and relaxed",
         "progression": "Carry the cue into easy runs."},
    ],
))
