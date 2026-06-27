"""gaitlab — a pure-Python running gait analysis engine.

Stdlib only (math, statistics) so it runs anywhere Python does, with zero installs,
and the math is unit-testable without a browser or a pose model.

Pipeline:  PoseSequence  ->  smooth  ->  gait events  ->  metrics  ->  asymmetry
           ->  target scoring  ->  rule-based feedback  ->  AnalysisResult

The only "source" coupling is the normalized pose schema (see schema.py); RTMPose,
MediaPipe, and the synthetic generator all produce the same PoseSequence, so the
engine never needs to know which one fed it.
"""

from .schema import PoseSequence, KEYPOINTS, VIEWS, SCHEMA_VERSION
from .analyze import analyze, AnalysisResult

__all__ = [
    "PoseSequence",
    "KEYPOINTS",
    "VIEWS",
    "SCHEMA_VERSION",
    "analyze",
    "AnalysisResult",
]
