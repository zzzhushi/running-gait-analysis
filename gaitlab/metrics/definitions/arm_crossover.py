"""Arm crossover — hands swinging across the body midline, rear view (boolean)."""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    hip_order = med([
        ctx.seq.xy(f, "r_hip")[0] - ctx.seq.xy(f, "l_hip")[0]
        for f in range(ctx.n)
    ])
    orientation = -1.0 if hip_order == hip_order and hip_order < 0 else 1.0
    cross = sum(1 for f in range(ctx.n)
                if (ctx.seq.xy(f, "l_wrist")[0] - ctx.seq.xy(f, "mid_hip")[0]) * orientation > 0
                or (ctx.seq.xy(f, "r_wrist")[0] - ctx.seq.xy(f, "mid_hip")[0]) * orientation < 0)
    return cross > ctx.n * 0.25


register(MetricDef(
    key=MetricKey.ARM_CROSSOVER,
    label="Arm crossover",
    unit="",
    good=(None, None),
    warn=(None, None),
    note="Whether either wrist crosses the pelvis-relative image midline in more than 25% of frames.",
    confidence="low",
    evidence_level="experimental",
    views=("rear",),
    scored=False,
    is_boolean=True,
    compute=_compute,
    keypoints=("mid_hip", "l_hip", "r_hip", "l_wrist", "r_wrist"),
    card_visibility="always",
))
