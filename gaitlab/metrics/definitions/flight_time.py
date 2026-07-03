"""Flight time — time both feet are off the ground per step (an fps-limited
estimate derived from cadence and mean contact time), side view."""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    cadence = ctx.ev.cadence_spm
    ct_vals = [ctx.ev.contact_time[s] * 1000.0 for s in ("l", "r") if s in ctx.ev.contact_time]
    if cadence != cadence or cadence <= 0 or not ct_vals:
        return float("nan")
    return max(0.0, 60000.0 / cadence - sum(ct_vals) / len(ct_vals))


register(MetricDef(
    key=MetricKey.FLIGHT_TIME,
    label="Flight time",
    unit="ms",
    good=(None, None),
    warn=(None, None),
    note="Time both feet are off the ground per step (fps-limited estimate).",
    confidence="moderate",
    views=("side",),
    scored=False,
    compute=_compute,
    card_status="info",
))
