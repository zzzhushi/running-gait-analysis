"""Left/right asymmetry from the per-side metric values.

The metrics tracked here (and their label/unit/direction) are derived from the
registry's `per_side` flag — see gaitlab/metrics/spec.py:asym_metrics() — not a
hand-maintained list, so a metric's label/unit can't drift out of sync between
its own card and its asymmetry row.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import spec as registry
from .defs import METRIC_DEFS
from .keys import MetricKey


def diff_pct(l: float, r: float) -> float:
    """Symmetric percent difference relative to the mean absolute magnitude.

    `abs(l-r) / mean(abs(l), abs(r))` is order-independent and supports signed
    angle metrics. Treat two near-zero values as equal because the ratio is unstable there.
    """
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
    for defn in registry.asym_metrics():
        key = defn.key
        l = per_side["l"].get(key.value)
        r = per_side["r"].get(key.value)
        if l is None or r is None or l != l or r != r:
            continue
        d = diff_pct(l, r)
        status = t.status(d)
        # Suppress asymmetry only when an actual target band says both sides are healthy.
        # Bandless metrics use "good" as a status sentinel, not evidence of health.
        indiv_t = _targets.get(key)
        has_band = indiv_t is not None and tuple(indiv_t.good) != (None, None)
        if has_band and status != "good":
            if indiv_t.status(l) == "good" and indiv_t.status(r) == "good":
                status = "good"
        out.append({
            "key": key,
            "label": defn.label,
            "unit": defn.unit,
            "left": round(l, 2),
            "right": round(r, 2),
            "diff_pct": round(d, 1),
            "status": status,
            "worse_side": _worse_side(l, r, defn.asym_direction),
        })
    out.sort(key=lambda a: a["diff_pct"], reverse=True)
    return out


def overall_diff(asym: List[dict]) -> float:
    flagged = [a["diff_pct"] for a in asym if a["status"] in ("warn", "bad")]
    if not flagged:
        return 0.0
    return sum(flagged) / len(flagged)
