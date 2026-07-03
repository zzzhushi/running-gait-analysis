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
    label="Trunk Pelvis Rotation",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Shoulder-vs-pelvis counter-rotation — a low-confidence 2-D rear-view proxy.",
    confidence="moderate",
    views=("rear",),
    scored=False,
    compute=_compute,
    card_status="info",
))
