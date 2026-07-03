"""Vertical oscillation in absolute centimeters — only available once a standing
height or leg length calibrates pixels to real-world units. Informational only.
"""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    if not ctx.cal["px_per_cm"]:
        return None
    return ctx.vertical_oscillation_px() / ctx.cal["px_per_cm"]


register(MetricDef(
    key=MetricKey.VERTICAL_OSCILLATION_CM,
    label="Vertical oscillation",
    unit="cm",
    good=(None, None),
    warn=(None, None),
    note="Absolute hip bounce (from your height).",
    confidence="moderate",
    views=("side",),
    scored=False,
    compute=_compute,
    card_visibility="conditional",
))
