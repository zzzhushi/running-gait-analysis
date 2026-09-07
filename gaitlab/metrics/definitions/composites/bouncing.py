"""Exploratory co-occurrence of vertical displacement and cadence heuristics.

The numeric cutoffs are retained only to make the former prototype pattern
observable; they are not population targets or a validated construct.
"""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="bouncing",
    view="side",
    all_of=(
        cond(MetricKey.VERTICAL_OSCILLATION, ">", value=18),
        cond(MetricKey.CADENCE, "<", value=170),
    ),
    severity="low",
    title="Exploratory pattern: vertical displacement",
    detail=(
        "Hip vertical travel was ~{vertical_oscillation:.0f}% of leg length and cadence was "
        "~{cadence:.0f} spm in the same stride. This is descriptive and does not measure energy waste."
    ),
    cue="Compare vertical displacement only at matched speed and camera setup.",
    drill="",
    supersedes=(),
))
