"""Exploratory co-occurrence of three sagittal-plane heuristics."""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="overstriding",
    view="side",
    all_of=(
        cond(MetricKey.OVERSTRIDE, ">", value=8),
        cond(MetricKey.HIP_EXTENSION, "<", value=10),
        cond(MetricKey.CADENCE, "<", value=170),
    ),
    severity="low",
    title="Exploratory pattern: forward foot placement",
    detail=(
        "Forward foot placement was ~{overstride:.0f}% of leg length, hip extension was "
        "~{hip_extension:.0f}°, and cadence was ~{cadence:.0f} spm in the same stride. "
        "This is a descriptive pattern, not a force or injury measurement."
    ),
    cue="Compare this pattern at the same speed across repeated recordings.",
    drill="",
    supersedes=(),
))
