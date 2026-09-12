"""Vertical oscillation in absolute centimeters — only available once a standing
height or leg length calibrates pixels to real-world units. Informational only.
"""

from __future__ import annotations

from ..keys import MetricKey
from ..reference_models import population_reference
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    if not ctx.cal.px_per_cm:
        return None
    return ctx.vertical_oscillation_px() / ctx.cal.px_per_cm


register(MetricDef(
    key=MetricKey.VERTICAL_OSCILLATION_CM,
    label="Vertical oscillation",
    unit="cm",
    good=(None, None),
    warn=(None, None),
    note="Absolute mid-hip image displacement after scale calibration; camera motion remains a source of error.",
    confidence="low",
    evidence_level="screening",
    reference_ids=("Malisoux2023",),
    views=("side",),
    scored=False,
    compute=_compute,
    keypoints=("mid_hip",),
    requires_events=True,
    reference_fn=lambda profile: population_reference("vertical_oscillation_cm", profile),
    card_visibility="conditional",
))
