"""Peak sagittal hip-extension proxy: thigh relative to trunk."""

from __future__ import annotations

from ..ctx import per_stride_max
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    behind = [-v for v in ctx.hip_flexion_series(side)]
    return per_stride_max(behind, ctx.ev.strikes[side])


register(MetricDef(
    key=MetricKey.HIP_EXTENSION,
    label="Hip extension (peak)",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note="Peak thigh extension relative to the trunk in the sagittal image plane; descriptive, not a strength or flexibility diagnosis.",
    higher_is_better=True,
    confidence="moderate",
    evidence_level="screening",
    reference_ids=("Hensley2022", "Leporace2023", "Cronin2023"),
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="higher_better",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_low",
    keypoints=("neck", "mid_hip", "l_hip", "l_knee", "r_hip", "r_knee"),
    event_phase="all",
    requires_events=True,
    card_per_side_key="hip_extension",
))
