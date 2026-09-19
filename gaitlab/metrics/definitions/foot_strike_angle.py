"""Foot-strike angle — heel/midfoot/forefoot classification, side view.

No good/warn band by design: no single strike pattern is inherently better —
it's the overstride that matters (see the note below). Because both bounds are
None, `status()` always reports "good", so this never fires a coaching finding
on its own; its finding_text exists only for the heavy_heelstrike composite,
which builds its own text but keeps this declared here for reference.
"""

from __future__ import annotations

import math

from ..ctx import median
from ..keys import MetricKey
from ..spec import MetricDef, register


def _avg_xy(seq, f, name, half_window=1):
    """Position averaged over frames [f-half_window, f+half_window], clamped to the
    clip. LIFT_FRACTION's contact frame can land one frame either side of the true
    contact depending on tracking noise; averaging over that window keeps a single
    frame's quantization from flipping the heel/midfoot/forefoot classification.
    """
    lo, hi = max(0, f - half_window), min(seq.n - 1, f + half_window)
    pts = [seq.xy(i, name) for i in range(lo, hi + 1)]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _compute(ctx, side):
    """Median sagittal foot-to-horizontal angle at initial contact.

    Positive means the toe is above the heel (rearfoot-oriented); negative means
    the toe is below it (forefoot-oriented). Image y increases downward, hence `-dy`.
    This follows Altman and Davis' segment-to-ground definition
    (DOI 10.1016/j.gaitpost.2011.09.104), but uses image horizontal and cannot apply
    their standing-angle calibration.
    """
    vals = []
    for s in ctx.ev.strikes[side]:
        heel = _avg_xy(ctx.seq, s, f"{side}_heel")
        toe = _avg_xy(ctx.seq, s, f"{side}_big_toe")
        dx = (toe[0] - heel[0]) * ctx.facing
        dy = toe[1] - heel[1]
        vals.append(math.degrees(math.atan2(-dy, abs(dx) + 1e-6)))
    return median(vals)


register(MetricDef(
    key=MetricKey.FOOT_STRIKE_ANGLE,
    label="Foot-strike angle",
    unit="deg",
    good=(None, None),
    warn=(None, None),
    note=(
        "Where your foot first contacts: heel, midfoot, or forefoot. None is inherently bad — "
        "it's the overstride that matters."
    ),
    confidence="moderate",
    views=("side",),
    scored=False,
    per_side=True,
    asym_direction="neutral",
    compute=_compute,
    per_side_compute=True,
    aggregate="median",
    finding_text={
        "any": {
            "title": "Heavy heel-strike with overstriding",
            "detail": (
                "You land clearly on the heel with the foot well ahead of you. Heel contact itself "
                "isn't bad, but combined with overstriding it amplifies braking and impact."
            ),
            "cue": "Fixing the overstride (land under your hips) usually softens the heel-strike on its own.",
            "drill": "Same high-cadence strides as above; let foot-strike self-correct.",
        },
    },
))
