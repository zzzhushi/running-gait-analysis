"""Re-exports from defs for backward compatibility and convenient imports.

The scoring logic (status(), score(), personalize()) now lives in defs.py alongside
the threshold data it depends on. This module re-exports the public API so call-sites
can import from either place.
"""

from .defs import METRIC_DEFS, MetricDef, personalize  # noqa: F401

# Backward-compat alias used in some import paths.
TARGETS = METRIC_DEFS
