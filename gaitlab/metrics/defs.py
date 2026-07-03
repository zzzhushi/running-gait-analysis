"""Compatibility facade over the metric registry.

`MetricDef`/`METRIC_DEFS`/`value_confidence`/`personalize` used to be defined
here directly; the single source of truth has moved to one module per metric
under gaitlab/metrics/definitions/ (see gaitlab/metrics/spec.py for the record
shape). This module just re-exports the registry under the names existing
callers already use, importing `definitions` for its registration side effect.
"""

from __future__ import annotations

from typing import Dict, Optional

from . import definitions  # noqa: F401  (import side effect: registers every metric)
from .keys import MetricKey
from .spec import BAD, GOOD, WARN, MetricDef, all_metrics

__all__ = ["MetricDef", "METRIC_DEFS", "GOOD", "WARN", "BAD", "value_confidence", "personalize"]

METRIC_DEFS: Dict[MetricKey, MetricDef] = all_metrics()


def value_confidence(defn: MetricDef, value: float) -> str:
    """Value-dependent confidence for a metric reading; delegates to the
    metric's own `value_confidence_fn` (see e.g. definitions/pelvic_drop.py)."""
    return defn.value_confidence(value)


def personalize(profile: Optional[dict]) -> Dict[MetricKey, MetricDef]:
    """A copy of METRIC_DEFS with any metric's bands adjusted for the runner's
    profile (see each metric's `personalize_fn`, e.g. cadence and pelvic_drop)."""
    if not profile:
        return dict(METRIC_DEFS)
    return {key: defn.personalize(profile) for key, defn in METRIC_DEFS.items()}
