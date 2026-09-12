"""Descriptive temporal outputs derived from the estimated event sequence."""

from __future__ import annotations

from statistics import mean, median, pstdev

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _event_value(name, scale=1.0):
    def compute(ctx, side):
        value = getattr(ctx.ev, name).get(side)
        return value * scale if value is not None else float("nan")
    return compute


def _swing(ctx, side):
    stride = ctx.ev.stride_time.get(side)
    contact = ctx.ev.contact_time.get(side)
    return (stride - contact) * 1000.0 if stride is not None and contact is not None else float("nan")


def _cv(values):
    values = [v for v in values if v > 0]
    if len(values) >= 3:
        center = median(values)
        values = [v for v in values if center * 0.75 <= v <= center * 1.25]
    return pstdev(values) / mean(values) * 100.0 if len(values) >= 3 else float("nan")


def _cadence_cv(ctx, side=None):
    intervals = ctx.ev.step_times["l"] + ctx.ev.step_times["r"]
    return _cv([60.0 / value for value in intervals])


def _contact_cv(ctx, side=None):
    return _cv(ctx.ev.contact_times["l"] + ctx.ev.contact_times["r"])


_EVENT_KPS = ("l_ankle", "r_ankle", "l_heel", "r_heel", "l_big_toe", "r_big_toe")

for key, label, compute in (
    (MetricKey.STEP_TIME, "Step time", _event_value("step_time", 1000.0)),
    (MetricKey.STRIDE_TIME, "Stride time", _event_value("stride_time", 1000.0)),
    (MetricKey.SWING_TIME, "Swing time", _swing),
):
    register(MetricDef(
        key=key, label=label, unit="ms", good=(None, None), warn=(None, None),
        note=f"Median {label.lower()} from observed gait events; report descriptively and compare at the same speed.",
        confidence="low" if key == MetricKey.SWING_TIME else "moderate",
        evidence_level="experimental" if key == MetricKey.SWING_TIME else "screening",
        views=("side", "rear"),
        reference_ids=("Patoz2021", "Malisoux2023"),
        scored=False, per_side=True, compute=compute, per_side_compute=True,
        keypoints=_EVENT_KPS, event_phase="events", card_per_side_key=key.value,
    ))

register(MetricDef(
    key=MetricKey.CADENCE_CV, label="Step-rate variability", unit="CV%",
    good=(None, None), warn=(None, None),
    note="Coefficient of variation across observed step intervals; requires at least three intervals.",
    confidence="low", evidence_level="experimental", views=("side", "rear"),
    reference_ids=("Patoz2021",),
    scored=False, compute=_cadence_cv, keypoints=_EVENT_KPS, event_phase="events",
    card_visibility="conditional",
))

register(MetricDef(
    key=MetricKey.CONTACT_TIME_CV, label="Contact-time variability", unit="CV%",
    good=(None, None), warn=(None, None),
    note="Coefficient of variation across observed contacts; requires at least three complete stances.",
    confidence="low", evidence_level="experimental", views=("side",), scored=False,
    reference_ids=("Patoz2021",),
    compute=_contact_cv, keypoints=_EVENT_KPS, event_phase="events",
    card_visibility="conditional",
))
