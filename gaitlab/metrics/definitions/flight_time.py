"""Flight time — time both feet are off the ground per step (an fps-limited
estimate derived from cadence and mean contact time), side view."""

from __future__ import annotations

from ..keys import MetricKey
from ..reference_models import population_reference
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    vals = [ctx.ev.flight_time[s] * 1000.0 for s in ("l", "r") if s in ctx.ev.flight_time]
    return sum(vals) / len(vals) if vals else float("nan")


register(MetricDef(
    key=MetricKey.FLIGHT_TIME,
    label="Flight time",
    unit="ms",
    good=(None, None),
    warn=(None, None),
    note="Time both feet are off the ground per step (fps-limited estimate).",
    confidence="low",
    evidence_level="experimental",
    reference_ids=("Patoz2021", "Malisoux2023"),
    views=("side",),
    scored=False,
    compute=_compute,
    keypoints=("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe"),
    event_phase="events",
    reference_fn=lambda profile: population_reference("flight_time", profile),
    card_status="info",
))
