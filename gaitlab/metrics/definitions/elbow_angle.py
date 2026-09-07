"""Descriptive elbow angle in a side view."""

from __future__ import annotations

from ...core import geometry as geo
from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    return med([geo.angle_3pt(ctx.seq.xy(f, f"{side}_shoulder"), ctx.seq.xy(f, f"{side}_elbow"),
                               ctx.seq.xy(f, f"{side}_wrist"))
                for f in range(ctx.n)])


register(MetricDef(
    key=MetricKey.ELBOW_ANGLE,
    label="Elbow angle",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Median 2-D shoulder–elbow–wrist angle across the clip; occlusion can differ by side.",
    confidence="low",
    evidence_level="experimental",
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    keypoints=("l_shoulder", "l_elbow", "l_wrist", "r_shoulder", "r_elbow", "r_wrist"),
    card_per_side_key="elbow_angle",
))
