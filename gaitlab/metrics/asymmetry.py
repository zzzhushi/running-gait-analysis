"""Left/right asymmetry from the per-side metric values."""

from __future__ import annotations

from typing import Dict, List, Optional

from .defs import METRIC_DEFS
from .keys import MetricKey

# Per-side metrics compared left vs right. Label, unit, and direction all come from
# each key's own MetricDef (label/unit/asym_direction) — not duplicated here — so an
# edit to METRIC_DEFS can't silently drift out of sync with the asymmetry table.
ASYM_METRICS = [
    MetricKey.KNEE_FLEXION_MIDSTANCE,
    MetricKey.KNEE_FLEXION_CONTACT,
    MetricKey.OVERSTRIDE,
    MetricKey.FOOT_STRIKE_ANGLE,
    MetricKey.CONTACT_TIME_MS,
    MetricKey.HIP_EXTENSION,
    MetricKey.KNEE_DRIVE,
    MetricKey.ARM_SWING,
    MetricKey.HEEL_RECOVERY,
    MetricKey.STRIDE_LENGTH,
    MetricKey.STEP_LENGTH,
    MetricKey.PELVIC_DROP,
    MetricKey.HIP_ADDUCTION,
    MetricKey.PRONATION,
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
    _targets = targets or METRIC_DEFS
    t = _targets[MetricKey.ASYMMETRY]
    out: List[dict] = []
    if not per_side or "l" not in per_side or "r" not in per_side:
        return out
    for key in ASYM_METRICS:
        defn = _targets.get(key) or METRIC_DEFS[key]
        label, unit, direction = defn.label, defn.unit, defn.asym_direction
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
