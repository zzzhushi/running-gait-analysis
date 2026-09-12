"""Arm swing — fore-aft wrist excursion relative to the shoulder, side view.
Informational only; tracked for asymmetry but not shown per-side on the card."""

from __future__ import annotations

from ...core import geometry as geo
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    rel = [(ctx.seq.xy(f, f"{side}_wrist")[0] - ctx.seq.xy(f, f"{side}_shoulder")[0]) * ctx.facing
           for f in range(ctx.n)]
    return geo.peak_to_peak(rel) / ctx.leg * 100.0


register(MetricDef(
    key=MetricKey.ARM_SWING,
    label="Arm swing",
    unit="%leg",
    good=(None, None),
    warn=(None, None),
    note="Peak-to-peak sagittal wrist displacement relative to the same-side shoulder, normalized to leg length.",
    confidence="low",
    evidence_level="experimental",
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    keypoints=("l_shoulder", "r_shoulder", "l_wrist", "r_wrist"),
))
