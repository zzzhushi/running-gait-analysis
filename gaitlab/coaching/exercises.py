"""Corrective exercise plan builder.

Exercise lists are defined in gaitlab/metrics/defs.py — edit them there.
This module reads from METRIC_DEFS and assembles a deduped, prioritized plan
from the structured findings.
"""

from __future__ import annotations

from typing import List

from ..metrics.defs import METRIC_DEFS

# Aliases: map raw metric/title keys to the MetricDef key that holds exercises.
ALIASES = {
    "contact_time_ms": "contact_time",
    "foot_strike_angle": "overstride",
    "knee_flexion_contact": "knee_flexion_midstance",
    "stride_length": "asymmetry",
}


def build_plan(findings: List[dict], limit: int = 5) -> List[dict]:
    """Turn the prioritized findings into a deduped corrective exercise plan."""
    seen = set()
    plan: List[dict] = []
    for f in findings:
        if f.get("severity") not in ("high", "med", "low"):
            continue
        key = "asymmetry" if str(f.get("title", "")).startswith("Left/right") else f.get("metric")
        key = ALIASES.get(key, key)
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
