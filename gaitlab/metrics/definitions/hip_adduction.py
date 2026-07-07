"""Hip adduction (estimate) — how far the thigh drifts toward the midline at
midstance, rear view. The frontal-plane companion to pelvic_drop; see
composites/lateral_chain.py for the combined finding when both are elevated.

Low-confidence 2-D estimate, same footing as pronation.py: tech_requirements.md
§7.3/§10 rejects true knee valgus from a single rear camera as unreliable (a 2-D
projection can't separate genuine frontal-plane collapse from apparent-width
changes at this angle). Confidence is pinned "low" regardless of magnitude and
it's excluded from the headline score (scored=False) — surfaced as a prompt to
look closer, never a scored verdict.
"""

from __future__ import annotations

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register
from ...core import geometry as geo


def _compute(ctx, side):
    mids = ctx.ev.midstance(side) or list(range(0, ctx.n, max(1, ctx.n // 8)))
    vals = []
    for f in mids:
        hip = ctx.seq.xy(f, f"{side}_hip")
        knee = ctx.seq.xy(f, f"{side}_knee")
        mid_x = ctx.seq.xy(f, "mid_hip")[0]
        toward_mid = 1.0 if mid_x >= hip[0] else -1.0
        vals.append(geo.signed_lean(hip, knee, toward_mid))
    return med(vals)


register(MetricDef(
    key=MetricKey.HIP_ADDUCTION,
    label="Hip adduction (estimate)",
    unit="deg",
    good=(None, 8),
    warn=(None, 12),
    note=(
        "Estimated thigh drift toward the midline at midstance. This is a low-confidence 2-D "
        "rear-view estimate (true knee valgus needs a view this camera angle can't give) — treat "
        "it as a flag to look closer, not a measurement."
    ),
    confidence="low",
    views=("rear",),
    scored=False,  # low confidence, excluded from headline score — see module docstring
    per_side=True,
    asym_direction="higher_worse",
    compute=_compute,
    per_side_compute=True,
    aggregate="worst_high",
    keypoints=("l_hip", "l_knee", "r_hip", "r_knee"),
    foi="max_pelvic_drop",
    card_per_side_key="hip_adduction",
    value_confidence_fn=lambda value: "low",
    finding_text={
        "high": {
            "title": "Possible hip/knee collapse inward (estimate)",
            "detail": (
                "Your thigh appears to drift inward ~{value:.0f}° toward the midline at midstance. This "
                "is a low-confidence 2-D rear-view estimate, so treat it as a prompt to look closer "
                "rather than a verdict — often traces to the hip abductors when it's real."
            ),
            "cue": "Run 'knees tracking straight' — imagine your knee aiming over your second toe.",
            "drill": "Hip-abductor strength: side planks, banded hip-hikes/clamshells, single-leg squats, 3×/week.",
        },
    },
    exercises=[
        {"name": "Side planks",
         "why": "Builds lateral hip/core endurance to resist the thigh collapsing in.",
         "dose": "3×30s/side",
         "progression": "Add top-leg raises."},
        {"name": "Banded clamshells / hip-hikes",
         "why": "Directly trains the hip abductors that control adduction.",
         "dose": "3×12/side",
         "progression": "Add load / standing on a step."},
        {"name": "Single-leg squats",
         "why": "Controls hip + knee alignment under bodyweight on one leg.",
         "dose": "3×8/side",
         "progression": "Lower box / add weight."},
    ],
))
