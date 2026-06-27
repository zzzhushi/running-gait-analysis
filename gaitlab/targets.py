"""Target ranges + scoring for each metric.

Values are evidence-informed heuristics drawn from running-biomechanics literature
and coaching practice (cadence ~170-185 spm; midstance knee flexion ~45 deg; trunk
lean ~5-10 deg; pelvic drop concerning >~10 deg; ground contact ~200-250 ms; gait
asymmetry concerning >~10%). They are intentionally configurable in one place so the
thresholds can be tuned without touching the metric or feedback code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

GOOD, WARN, BAD = "good", "warn", "bad"


@dataclass
class Target:
    key: str
    label: str
    unit: str
    # Inclusive "good" band. Use None for an open end.
    good: Tuple[Optional[float], Optional[float]]
    # Inclusive "acceptable/warn" band (wider). Outside this -> bad.
    warn: Tuple[Optional[float], Optional[float]]
    # Plain-language note about what "good" looks like.
    note: str = ""
    higher_is_better: Optional[bool] = None  # for display arrows only

    def status(self, value: float) -> str:
        if value is None or value != value:  # NaN
            return WARN
        if _within(value, self.good):
            return GOOD
        if _within(value, self.warn):
            return WARN
        return BAD

    def score(self, value: float) -> float:
        """0..100 score for this metric (100 = ideal mid-band)."""
        if value is None or value != value:
            return 50.0
        s = self.status(value)
        if s == GOOD:
            return 100.0
        # Distance past the good band, relative to the warn margin.
        lo_g, hi_g = self.good
        lo_w, hi_w = self.warn
        if lo_g is not None and value < lo_g:
            span = (lo_g - lo_w) if lo_w is not None else (lo_g if lo_g else 1.0)
            frac = (lo_g - value) / span if span else 1.0
        elif hi_g is not None and value > hi_g:
            span = (hi_w - hi_g) if hi_w is not None else (hi_g if hi_g else 1.0)
            frac = (value - hi_g) / span if span else 1.0
        else:
            frac = 0.0
        frac = max(0.0, min(1.5, frac))
        return max(0.0, 100.0 - 55.0 * frac)


def _within(value: float, band: Tuple[Optional[float], Optional[float]]) -> bool:
    lo, hi = band
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


TARGETS = {
    "cadence": Target(
        "cadence", "Cadence", "spm",
        good=(170, 185), warn=(160, 195),
        note="Most runners are efficient at 170-185 steps/min. Low cadence usually means overstriding.",
        higher_is_better=True,
    ),
    "trunk_lean": Target(
        "trunk_lean", "Trunk lean", "deg",
        good=(5, 12), warn=(0, 16),
        note="A slight forward lean from the ankles (~5-12 deg) helps. Upright = braking; too far = back load.",
    ),
    "knee_flexion_midstance": Target(
        "knee_flexion_midstance", "Knee flexion (midstance)", "deg",
        good=(38, 50), warn=(28, 58),
        note="~40-50 deg of knee bend at midstance absorbs landing shock. Stiff knees jar the joints.",
    ),
    "overstride": Target(
        "overstride", "Overstride", "%leg",
        good=(None, 8), warn=(None, 15),
        note="Foot should land close to under your hips. Landing far ahead (>~8% of leg length) brakes you.",
    ),
    "vertical_oscillation": Target(
        "vertical_oscillation", "Vertical oscillation", "%leg",
        good=(None, 12), warn=(None, 18),
        note="Bouncing wastes energy. Lower vertical travel of the hips is generally more economical.",
    ),
    "pelvic_drop": Target(
        "pelvic_drop", "Pelvic drop", "deg",
        good=(None, 6), warn=(None, 10),
        note="The hip of the swinging leg dropping >~10 deg points to weak hip stabilizers (injury risk).",
    ),
    "contact_time": Target(
        "contact_time", "Ground contact time", "ms",
        good=(None, 250), warn=(None, 300),
        note="Efficient runners spend ~200-250 ms on the ground per step. Long contact = less reactive.",
    ),
    "step_width": Target(
        "step_width", "Step width / crossover", "%leg",
        good=(2, 14), warn=(0, 22),
        note="Feet should not cross the midline. Crossover narrows your base and stresses the IT band.",
    ),
    "lateral_trunk_sway": Target(
        "lateral_trunk_sway", "Lateral trunk sway", "%leg",
        good=(None, 8), warn=(None, 12),
        note="Side-to-side lean of the upper body. A lot of sway often follows hip drop or a weak core.",
    ),
    "asymmetry": Target(
        "asymmetry", "Left/right asymmetry", "%",
        good=(None, 5), warn=(None, 10),
        note="Under ~5% difference left-to-right is normal. Over ~10% is worth addressing.",
    ),
}


def target_for(key: str) -> Optional[Target]:
    return TARGETS.get(key)
