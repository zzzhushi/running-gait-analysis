"""Left/right asymmetry from the per-side metric values."""

from __future__ import annotations

from typing import Dict, List, Optional

from .targets import TARGETS

# key, label, unit, direction ("higher_better" | "higher_worse" | "neutral")
ASYM_METRICS = [
    ("knee_flexion_midstance", "Knee flexion (midstance)", "deg", "higher_better"),
    ("knee_flexion_contact", "Knee flexion (contact)", "deg", "neutral"),
    ("overstride", "Overstride", "%leg", "higher_worse"),
    ("foot_strike_angle", "Foot-strike angle", "deg", "neutral"),
    ("contact_time_ms", "Ground contact time", "ms", "higher_worse"),
    ("hip_extension", "Hip extension", "deg", "higher_better"),
    ("knee_drive", "Knee drive", "deg", "higher_better"),
    ("arm_swing", "Arm swing", "%leg", "neutral"),
    ("heel_recovery", "Heel recovery", "%leg", "neutral"),
    ("stride_length", "Stride length", "m", "higher_better"),
    ("step_length", "Step length", "m", "higher_better"),
    ("pelvic_drop", "Pelvic drop", "deg", "higher_worse"),
    ("pronation", "Pronation (est.)", "deg", "higher_worse"),
]


def diff_pct(l: float, r: float) -> float:
    if l != l or r != r:
        return float("nan")
    denom = (abs(l) + abs(r)) / 2.0
    if denom < 1e-6:
        return 0.0
    return abs(l - r) / denom * 100.0


def _worse_side(l: float, r: float, direction: str) -> str:
    if direction == "higher_better":
        return "left" if l < r else "right"
    if direction == "higher_worse":
        return "left" if l > r else "right"
    return "left" if abs(l) > abs(r) else "right"


def compute(per_side: Dict[str, Dict[str, float]], targets: Optional[Dict] = None) -> List[dict]:
    _targets = targets or TARGETS
    t = _targets["asymmetry"]
    out: List[dict] = []
    if not per_side or "l" not in per_side or "r" not in per_side:
        return out
    for key, label, unit, direction in ASYM_METRICS:
        l = per_side["l"].get(key)
        r = per_side["r"].get(key)
        if l is None or r is None or l != l or r != r:
            continue
        d = diff_pct(l, r)
        status = t.status(d)
        # diff_pct explodes when values are near zero (e.g. L=0° R=3° → 200%).
        # Suppress the flag when both sides are individually within the good target band:
        # if both values are healthy, a % difference between them isn't clinically meaningful.
        indiv_t = _targets.get(key)
        if indiv_t is not None and status != "good":
            if indiv_t.status(l) == "good" and indiv_t.status(r) == "good":
                status = "good"
        out.append({
            "key": key,
            "label": label,
            "unit": unit,
            "left": round(l, 2),
            "right": round(r, 2),
            "diff_pct": round(d, 1),
            "status": status,
            "worse_side": _worse_side(l, r, direction),
        })
    out.sort(key=lambda a: a["diff_pct"], reverse=True)
    return out


def overall_diff(asym: List[dict]) -> float:
    flagged = [a["diff_pct"] for a in asym if a["status"] in ("warn", "bad")]
    if not flagged:
        return 0.0
    return sum(flagged) / len(flagged)
