"""Cadence — descriptive steps per minute from the event sequence."""

from __future__ import annotations

from ..keys import MetricKey
from ..reference_models import population_reference
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    return ctx.ev.cadence_spm


register(MetricDef(
    key=MetricKey.CADENCE,
    label="Cadence",
    unit="spm",
    good=(None, None),
    warn=(None, None),
    note="Step rate. Interpret against speed- and stature-matched observations, not a universal 180-spm target.",
    confidence="moderate",
    evidence_level="supported",
    reference_ids=("Oliveira2019", "Malisoux2023"),
    views=("side", "rear"),
    scored=False,
    compute=_compute,
    keypoints=("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="events",
    reference_fn=lambda profile: population_reference("cadence", profile),
))
