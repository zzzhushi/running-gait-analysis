"""Kinematic contact-time estimate, exposed as headline and per-side keys."""

from __future__ import annotations

from ..keys import MetricKey
from ..reference_models import population_reference
from ..spec import MetricDef, register


def _compute(ctx, side):
    if side not in ctx.ev.contact_time:
        return float("nan")
    return ctx.ev.contact_time[side] * 1000.0


register(MetricDef(
    key=MetricKey.CONTACT_TIME,
    label="Ground contact time",
    unit="ms",
    good=(None, None),
    warn=(None, None),
    note="Median kinematic contact-time estimate. Strongly speed-dependent and approximate without force data.",
    confidence="low",
    evidence_level="experimental",
    reference_ids=("Patoz2021", "Malisoux2023"),
    views=("side",),
    scored=False,
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high",
    keypoints=("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="events",
    card_per_side_key="contact_time_ms",
    card_status="info",
    # Provisional event anchor: keep the measurement visible, never let it
    # drive a finding or a score.
    trigger_fn=lambda *a: None,
    reference_fn=lambda profile: population_reference("contact_time", profile),
))

register(MetricDef(
    key=MetricKey.CONTACT_TIME_MS,
    label="Ground contact time",
    unit="ms",
    good=(None, None),
    warn=(None, None),
    note="Per-side contact time in milliseconds. Used for left/right asymmetry detection.",
    confidence="low",
    evidence_level="experimental",
    reference_ids=("Patoz2021",),
    views=("side",),
    scored=False,
    per_side=False,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    keypoints=("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="events",
    card_visibility="hidden",
))
