"""Foot-strike angle — heel/midfoot/forefoot classification, side view.

No good/warn band by design: no single strike pattern is inherently better —
it's the overstride that matters (see the note below). Because both bounds are
None, `status()` always reports "good", so this never fires a coaching finding
on its own; its finding_text exists only for the heavy_heelstrike composite,
which builds its own text but keeps this declared here for reference.
"""

from __future__ import annotations

import math

from ..ctx import med
from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side):
    vals = []
    for s in ctx.ev.strikes[side]:
        heel = ctx.seq.xy(s, f"{side}_heel")
        toe = ctx.seq.xy(s, f"{side}_big_toe")
        dx = (toe[0] - heel[0]) * ctx.facing
        dy = toe[1] - heel[1]
        vals.append(math.degrees(math.atan2(-dy, abs(dx) + 1e-6)))
    return med(vals)


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
