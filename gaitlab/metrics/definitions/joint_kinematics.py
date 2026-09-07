"""Additional sagittal-plane kinematics reported without universal target bands."""

from __future__ import annotations

from ..ctx import med, per_stride_max
from ..keys import MetricKey
from ..spec import MetricDef, register
from ...core import geometry as geo


def _knee_peak(ctx, side):
    return per_stride_max(ctx.knee_flexion_series(side), ctx.ev.strikes[side])


def _knee_excursion(ctx, side):
    series = ctx.knee_flexion_series(side)
    values = []
    for strike, toeoff in ctx.ev.stance[side]:
        segment = [v for v in series[strike:toeoff + 1] if v == v]
        if segment:
            values.append(max(segment) - min(segment))
    return med(values)


def _hip_flexion(ctx, side):
    return per_stride_max(ctx.hip_flexion_series(side), ctx.ev.strikes[side])


def _ankle_offset(ctx, frame, side):
    angle = geo.angle_3pt(
        ctx.seq.xy(frame, f"{side}_knee"),
        ctx.seq.xy(frame, f"{side}_ankle"),
        ctx.seq.xy(frame, f"{side}_big_toe"),
    )
    return 90.0 - angle if angle == angle else float("nan")


def _ankle_dorsiflexion(ctx, side):
    return med([_ankle_offset(ctx, f, side) for f in ctx.ev.midstance(side)])


def _ankle_plantarflexion(ctx, side):
    return med([-_ankle_offset(ctx, f, side) for f in ctx.ev.toeoffs[side]])


def _shank(ctx, side):
    return med([
        geo.signed_lean(ctx.seq.xy(f, f"{side}_ankle"), ctx.seq.xy(f, f"{side}_knee"), ctx.facing)
        for f in ctx.ev.strikes[side]
    ])


for key, label, note, compute, phase, kps in (
    (MetricKey.KNEE_FLEXION_PEAK, "Peak knee flexion", "Peak knee flexion within each stride.", _knee_peak, "all", ("l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle")),
    (MetricKey.KNEE_FLEXION_EXCURSION, "Knee flexion excursion", "Change in knee flexion from minimum to maximum during observed stance.", _knee_excursion, "events", ("l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle")),
    (MetricKey.HIP_FLEXION_PEAK, "Thigh flexion relative to trunk", "Peak sagittal thigh flexion relative to the trunk; this replaces the mislabeled knee-drive angle.", _hip_flexion, "all", ("neck", "mid_hip", "l_hip", "r_hip", "l_knee", "r_knee")),
    (MetricKey.ANKLE_DORSIFLEXION, "Ankle angle proxy (midstance)", "Signed 2-D shank-to-foot offset from a 90° image-plane neutral (positive=dorsiflexion, negative=plantarflexion); shoe geometry and out-of-plane motion limit validity.", _ankle_dorsiflexion, "midstance", ("l_knee", "r_knee", "l_ankle", "r_ankle", "l_big_toe", "r_big_toe")),
    (MetricKey.ANKLE_PLANTARFLEXION, "Ankle angle proxy (toe-off)", "Signed 2-D shank-to-foot offset from a 90° image-plane neutral (positive=plantarflexion, negative=dorsiflexion) at estimated toe-off.", _ankle_plantarflexion, "toeoff", ("l_knee", "r_knee", "l_ankle", "r_ankle", "l_big_toe", "r_big_toe")),
    (MetricKey.SHANK_ANGLE_CONTACT, "Shank angle at contact", "Sagittal shank angle relative to vertical at estimated initial contact.", _shank, "strike", ("l_knee", "r_knee", "l_ankle", "r_ankle")),
):
    register(MetricDef(
        key=key, label=label, unit="deg", good=(None, None), warn=(None, None), note=note,
        confidence="moderate" if key not in (MetricKey.ANKLE_DORSIFLEXION, MetricKey.ANKLE_PLANTARFLEXION) else "low",
        evidence_level="supported" if key in (MetricKey.KNEE_FLEXION_PEAK, MetricKey.KNEE_FLEXION_EXCURSION, MetricKey.SHANK_ANGLE_CONTACT) else "screening",
        reference_ids=("Hensley2022", "Leporace2023", "Cronin2023"),
        views=("side",), scored=False, per_side=True, compute=compute, per_side_compute=True,
        keypoints=kps, event_phase=phase, card_per_side_key=key.value,
        requires_events=key in (MetricKey.KNEE_FLEXION_PEAK, MetricKey.HIP_FLEXION_PEAK),
    ))
