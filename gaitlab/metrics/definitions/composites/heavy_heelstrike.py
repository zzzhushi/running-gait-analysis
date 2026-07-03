"""Heavy heel-strike with overstriding — heel contact alone isn't a fault, but
combined with overstriding it amplifies braking and impact.

foot_strike_angle has no good/warn band by design (no strike pattern is
inherently good or bad on its own — see its module), so its condition uses an
explicit literal rather than a band reference.
"""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="heavy_heelstrike",
    view="side",
    all_of=(
        cond(MetricKey.FOOT_STRIKE_ANGLE, ">", value=12),
        cond(MetricKey.OVERSTRIDE, ">", band="good_hi"),
    ),
    severity="med",
    title="Heavy heel-strike with overstriding",
    detail=(
        "You land clearly on the heel with the foot well ahead of you. Heel contact itself isn't bad, "
        "but combined with overstriding it amplifies braking and impact."
    ),
    cue="Fixing the overstride (land under your hips) usually softens the heel-strike on its own.",
    drill="High-cadence strides focusing on landing beneath you.",
    supersedes=("foot_strike_angle",),
))
