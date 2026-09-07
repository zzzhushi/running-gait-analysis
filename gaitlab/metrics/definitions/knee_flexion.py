"""Knee flexion — same smoothed per-side angle series, sampled at two different
gait events. Two metrics, one shared signal (see Ctx.knee_flexion_series), so
they live in one file rather than two.
"""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _midstance(ctx, side):
    kflex = ctx.knee_flexion_series(side)
    return med([kflex[m] for m in ctx.ev.midstance(side)])


def _contact(ctx, side):
    kflex = ctx.knee_flexion_series(side)
    return med([kflex[s] for s in ctx.ev.strikes[side]])


register(MetricDef(
    key=MetricKey.KNEE_FLEXION_MIDSTANCE,
    label="Knee flexion (midstance)",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Sagittal knee flexion at estimated midstance. Report descriptively because values vary with speed and protocol.",
    confidence="moderate",
    evidence_level="supported",
    reference_ids=("Hensley2022", "Leporace2023", "Cronin2023"),
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="higher_better",
    compute=_midstance,
    per_side_compute=True,
    aggregate="worst_low",
    keypoints=("l_hip", "l_knee", "l_ankle", "r_hip", "r_knee", "r_ankle"),
    event_phase="midstance",
    foi="l_midstance",
    card_per_side_key="knee_flexion_midstance",
))

register(MetricDef(
    key=MetricKey.KNEE_FLEXION_CONTACT,
    label="Knee flexion (contact)",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Sagittal knee flexion at estimated initial contact; descriptive only.",
    confidence="moderate",
    evidence_level="supported",
    reference_ids=("Hensley2022", "Leporace2023", "Cronin2023"),
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_contact,
    per_side_compute=True,
    keypoints=("l_hip", "l_knee", "l_ankle", "r_hip", "r_knee", "r_ankle"),
    event_phase="strike",
    card_visibility="always",
    card_per_side_key="knee_flexion_contact",
))
