"""Corrective exercise plan builder.

Exercises are defined on each metric's own module under
gaitlab/metrics/definitions/ — this module just reads METRIC_DEFS and
assembles a deduped, prioritized plan from the structured findings. A
finding's `metric` field is always a plain metric key (or "asymmetry" for a
left/right imbalance finding) — see gaitlab/coaching/feedback.py — so no
separate alias table is needed to resolve it back to a MetricDef.
"""

from __future__ import annotations

from typing import List

from ..metrics.defs import METRIC_DEFS


def build_plan(findings: List[dict], limit: int = 5) -> List[dict]:
    """Turn the prioritized findings into a deduped corrective exercise plan."""
    seen = set()
    plan: List[dict] = []
    for f in findings:
        if f.get("severity") not in ("high", "med", "low"):
            continue
        key = "asymmetry" if str(f.get("title", "")).startswith("Left/right") else f.get("metric")
        if not key or key in seen:
            continue
        mdef = METRIC_DEFS.get(key)
        if mdef is None or not mdef.exercises:
            continue
        seen.add(key)
        plan.append({
            "key": key,
            "title": f.get("title"),
            "severity": f.get("severity"),
            "exercises": mdef.exercises,
        })
        if len(plan) >= limit:
            break
    return plan
