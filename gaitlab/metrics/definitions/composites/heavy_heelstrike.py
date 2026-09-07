"""Exploratory co-occurrence of rearfoot contact and forward foot placement.

The heuristic does not infer loading, braking, injury risk, or a fault.
"""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="heavy_heelstrike",
    view="side",
    all_of=(
        cond(MetricKey.FOOT_STRIKE_ANGLE, ">", value=12),
        cond(MetricKey.OVERSTRIDE, ">", value=8),
    ),
    severity="low",
    title="Exploratory pattern: rearfoot contact with forward placement",
    detail=(
        "Rearfoot contact and forward foot placement crossed the prototype cutoffs in the same stride. "
        "Video alone does not establish braking or impact force."
    ),
    cue="Confirm camera level and review the contact frame before interpreting this pattern.",
    drill="",
    supersedes=(),
    min_confidence="low",
))
