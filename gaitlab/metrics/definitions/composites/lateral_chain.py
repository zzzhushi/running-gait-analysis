"""Lateral chain collapse — the pelvis drops toward the swinging leg while the
stance-side hip/knee estimate shows inward drift at the same time, rear view.

hip_adduction is a hedged, low-confidence 2-D estimate (see its module
docstring), so this composite is deliberately med (not high) severity and its
copy stays hedged — it's a "worth a closer look" pattern, not a confident
verdict, since one of its two inputs can't be measured reliably from this
camera angle.
"""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="lateral_chain",
    view="rear",
    all_of=(
        cond(MetricKey.PELVIC_DROP, ">", band="good_hi"),
        cond(MetricKey.HIP_ADDUCTION, ">", band="good_hi"),
    ),
    severity="med",
    title="Possible lateral hip collapse (weak stabilizers)",
    detail=(
        "Your pelvis drops (~{pelvic_drop:.0f}°) while the hip/knee estimate shows inward drift "
        "toward the midline (~{hip_adduction:.0f}°) at the same time. The inward-drift reading is a "
        "low-confidence estimate, but together this pattern is worth a closer look — it usually "
        "traces to weak hip abductors."
    ),
    cue="Run 'level hips, knees tracking straight' — resist both the drop and the inward collapse.",
    drill="Hip-abductor strength: side planks, banded hip-hikes/clamshells, single-leg squats, 3×/week.",
    supersedes=("pelvic_drop", "hip_adduction"),
))
