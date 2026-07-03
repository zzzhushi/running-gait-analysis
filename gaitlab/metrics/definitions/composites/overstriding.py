"""Overstriding / reaching — low cadence, limited hip extension, and landing
far ahead of the hips reinforce each other into one braking pattern."""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="overstriding",
    view="side",
    all_of=(
        cond(MetricKey.OVERSTRIDE, ">", band="good_hi"),
        cond(MetricKey.HIP_EXTENSION, "<", band="good_lo"),
        cond(MetricKey.CADENCE, "<", band="good_lo"),
    ),
    severity="high",
    title="Overstriding — quicken your cadence",
    detail=(
        "You're reaching out in front: the foot lands ~{overstride:.0f}% of a leg ahead of your hips, "
        "hip extension is limited (~{hip_extension:.0f}°), and cadence is low (~{cadence:.0f} spm). Together these "
        "brake you on every step and raise impact loading."
    ),
    cue="Lift cadence ~5-10% and let the foot land under your hips.",
    drill="High-cadence strides (6×20s) + couch stretch and glute bridges for hip extension.",
    supersedes=("overstride", "hip_extension", "cadence"),
))
