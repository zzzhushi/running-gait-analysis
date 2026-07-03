"""Left/right asymmetry — the meta-metric. Not computed from pose directly (its
value comes from gaitlab/metrics/asymmetry.py's diff-percent calculation); this
module just declares its band (used to score each per-metric asymmetry
percentage) and the generic single-leg-strength exercises for any asymmetry
finding, regardless of which metric it's about.
"""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register

register(MetricDef(
    key=MetricKey.ASYMMETRY,
    label="Left/right asymmetry",
    unit="%",
    good=(None, 5),
    warn=(None, 10),
    note="Under ~5% difference left-to-right is normal. Over ~10% is worth addressing.",
    confidence="high",
    views=("side", "rear"),
    scored=True,
    card_visibility="hidden",  # meta-metric: a band + exercises source, not its own card
    exercises=[
        {"name": "Single-leg strength (weaker side)",
         "why": "Closes a left/right gap by training the lagging side.",
         "dose": "Extra 1-2 sets on the weaker side (squats, calf raises, hip-hikes)",
         "progression": "Re-test in ~4 weeks; even up once matched."},
        {"name": "Single-leg balance",
         "why": "Improves one-sided control and proprioception.",
         "dose": "3×30s/side, weaker side first",
         "progression": "Eyes closed / unstable surface."},
    ],
))
