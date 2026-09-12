"""Registry metadata for descriptive left/right comparisons."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register

register(MetricDef(
    key=MetricKey.ASYMMETRY,
    label="Left/right comparison",
    unit="",
    good=(None, None),
    warn=(None, None),
    note="Raw side values and signed native-unit differences; no universal asymmetry threshold.",
    confidence="low",
    views=("side", "rear"),
    scored=False,
    card_visibility="hidden",
))
