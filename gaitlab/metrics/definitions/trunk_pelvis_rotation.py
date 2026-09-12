"""Trunk-pelvis counter-rotation — shoulder-line vs hip-line angle, rear view.
Low-confidence 2-D proxy; informational only, no coaching trigger."""

from __future__ import annotations

from ...core import geometry as geo
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    sh = ctx.shoulder_angle_series()
    tilt = ctx.pelvic_tilt_series()
    return geo.peak_to_peak([sh[f] - tilt[f] for f in range(ctx.n)])


register(MetricDef(
    key=MetricKey.TRUNK_PELVIS_ROTATION,
    label="Shoulder–pelvis frontal obliquity",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Difference between shoulder-line and hip-line angles in the image plane. This is not axial trunk–pelvis rotation.",
    confidence="low",
    evidence_level="experimental",
    views=("rear",),
    scored=False,
    compute=_compute,
    keypoints=("l_shoulder", "r_shoulder", "l_hip", "r_hip"),
    card_status="info",
))
