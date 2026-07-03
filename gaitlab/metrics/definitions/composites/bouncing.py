"""Bouncing — high vertical oscillation at a low cadence means drive is going
up instead of forward. Compares vertical oscillation against its WARN-band
edge (18%), not the good-band edge (12%), matching the original threshold.
"""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="bouncing",
    view="side",
    all_of=(
        cond(MetricKey.VERTICAL_OSCILLATION, ">", band="warn_hi"),
        cond(MetricKey.CADENCE, "<", band="good_lo"),
    ),
    severity="high",
    title="Bouncing — drive forward, not up",
    detail=(
        "Your hips travel ~{vertical_oscillation:.0f}% of a leg vertically each stride at a low cadence "
        "(~{cadence:.0f} spm), so drive is going up instead of forward."
    ),
    cue="Lift cadence and keep the crown of your head on a level line.",
    drill="Run-tall-past-a-rail (4×20s) and pogo hops (3×10).",
    supersedes=("vertical_oscillation", "cadence"),
))
