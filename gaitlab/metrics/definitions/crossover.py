"""Crossover gait — feet crossing the midline at contact, rear view (boolean).

Previously this fired by borrowing step_width's finding_text via a raw
`str(MetricKey.STEP_WIDTH)` — which on this interpreter returns the class-qualified
name ("MetricKey.STEP_WIDTH"), not the plain value, so the exercise-plan lookup
for this finding silently failed. Giving crossover its own key/text/exercises
(same content) fixes that at the root — the finding's `metric` is just its own
key, resolved the same way every other finding is.
"""

from __future__ import annotations

from ..keys import MetricKey
from ..spec import MetricDef, register


def _compute(ctx, side=None):
    _width, crossover = ctx.step_width_and_crossover()
    return crossover


def _trigger(defn, value, values, targets):
    return ("any", "med") if value else None


register(MetricDef(
    key=MetricKey.CROSSOVER,
    label="Crossover gait",
    unit="",
    good=(None, None),
    warn=(None, None),
    note="Feet crossing the body midline at contact narrows your base and stresses the IT band.",
    confidence="high",
    views=("rear",),
    scored=False,
    is_boolean=True,
    compute=_compute,
    trigger_fn=_trigger,
    card_visibility="hidden",
    finding_text={
        "any": {
            "title": "Crossover gait",
            "detail": (
                "Your feet cross toward the midline at contact, which narrows your base and twists "
                "the load through the knee and IT band."
            ),
            "cue": "Imagine running along two parallel rails, one foot on each.",
            "drill": "Banded lateral walks and single-leg balance to widen your base.",
        },
    },
    exercises=[
        {"name": "Two-rails cue runs",
         "why": "Widens a crossover gait.",
         "dose": "5×20s imagining a foot on each rail",
         "progression": "Keep it on easy runs."},
        {"name": "Banded lateral walks",
         "why": "Strengthens the base to stop crossing midline.",
         "dose": "3×12 steps/side",
         "progression": "Heavier band, lower stance."},
    ],
))
