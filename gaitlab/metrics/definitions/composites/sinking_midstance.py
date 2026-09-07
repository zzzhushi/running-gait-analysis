"""Exploratory co-occurrence of knee flexion and trunk lean at midstance."""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="sinking_midstance",
    view="side",
    all_of=(
        cond(MetricKey.KNEE_FLEXION_MIDSTANCE, ">", value=50),
        cond(MetricKey.TRUNK_LEAN, ">", value=16),
    ),
    severity="low",
    title="Exploratory pattern: flexed midstance",
    detail=(
        "Knee flexion was ~{knee_flexion_midstance:.0f}° and trunk lean was "
        "~{trunk_lean:.0f}° at the same midstance. This does not identify weakness or pathology."
    ),
    cue="Review the synchronized frame and compare repeated strides at the same speed.",
    drill="",
    supersedes=(),
))
