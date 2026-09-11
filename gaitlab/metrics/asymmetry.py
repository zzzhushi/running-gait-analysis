"""Descriptive left/right comparisons without universal asymmetry cutoffs."""

from __future__ import annotations

from typing import Dict, List, Optional

from . import spec as registry


def diff_pct(l: float, r: float) -> float:
    """Symmetry-index magnitude; unstable near zero and never used as a score."""
    if l != l or r != r:
        return float("nan")
    denom = (abs(l) + abs(r)) / 2.0
    if denom < 1e-6:
        return float("nan")
    return abs(l - r) / denom * 100.0


def compute(
    per_side: Dict[str, Dict[str, float]],
    confidences: Optional[Dict[str, str]] = None,
) -> List[dict]:
    out: List[dict] = []
    if not per_side or "l" not in per_side or "r" not in per_side:
        return out
    for defn in registry.asym_metrics():
        key = defn.key.value
        left = per_side["l"].get(key)
        right = per_side["r"].get(key)
        if left is None or right is None or left != left or right != right:
            continue
        delta = left - right
        ratio = diff_pct(left, right)
        mdc = defn.asymmetry_mdc
        interpretation = "descriptive"
        if mdc is not None:
            interpretation = "exceeds_mdc" if abs(delta) > mdc else "within_mdc"
        out.append({
            "key": key,
            "label": defn.label,
            "unit": defn.unit,
            "left": round(left, 2),
            "right": round(right, 2),
            "difference": round(delta, 2),
            "diff_pct": round(ratio, 1) if ratio == ratio else None,
            "ratio_caveat": "Percentage is unstable when values are near zero.",
            "mdc": mdc,
            "interpretation": interpretation,
            "status": "info",
            "confidence": (confidences or {}).get(key, "low"),
        })
    out.sort(key=lambda row: abs(row["difference"]), reverse=True)
    return out
