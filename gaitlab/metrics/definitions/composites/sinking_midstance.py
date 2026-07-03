"""Sinking into mid-stance — a collapsing knee combined with a forward-pitching
trunk signals the stance leg and core aren't holding the runner tall.

Note the trunk-lean condition compares against the WARN-band edge (16°), not
the good-band edge (12°) — this composite only fires once trunk lean is well
past merely-suboptimal, matching the original hand-tuned threshold.
"""

from __future__ import annotations

from ...keys import MetricKey
from ...spec import Composite, cond, register_composite

register_composite(Composite(
    id="sinking_midstance",
    view="side",
    all_of=(
        cond(MetricKey.KNEE_FLEXION_MIDSTANCE, ">", band="good_hi"),
        cond(MetricKey.TRUNK_LEAN, ">", band="warn_hi"),
    ),
    severity="high",
    title="Sinking into mid-stance",
    detail=(
        "Your knee collapses (~{knee_flexion_midstance:.0f}° flexion) while the trunk pitches forward "
        "(~{trunk_lean:.0f}°) at mid-stance — a sign the stance leg and core aren't holding you tall."
    ),
    cue="Run tall; don't sink into the stance leg.",
    drill="Glute bridges and anti-extension core work (dead bugs, planks).",
    supersedes=("knee_flexion_midstance", "trunk_lean"),
))
