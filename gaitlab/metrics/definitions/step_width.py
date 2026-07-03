"""Step width — lateral separation between the feet at contact, rear view.

Shares its per-strike ankle-separation loop with `crossover` (Ctx.step_width_and_crossover).
No independent trigger of its own: despite having a good/warn band, only the
discrete crossover event (crossover.py) raises a coaching finding — a merely
narrow-but-not-crossing step width is left as informational.
"""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    width, _crossover = ctx.step_width_and_crossover()
    return width


register(MetricDef(
    key=MetricKey.STEP_WIDTH,
    label="Step width / crossover",
    unit="%leg",
    good=(2, 14),
    warn=(0, 22),
    note="Feet should not cross the midline. Crossover narrows your base and stresses the IT band.",
    confidence="high",
    views=("rear",),
    scored=True,
    compute=_compute,
    trigger_fn=lambda *a: None,  # crossover.py raises the actual finding for this gait fault
))
