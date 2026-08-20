"""A PoseExtractor that needs no video, no model, and no subprocess.

Wraps gaitlab.synthetic.generate() — the same procedural pose generator the
demo runs and most of the test suite already use — so MockExtractor produces
exactly the kind of PoseSequence the engine is already exercised against,
rather than a second, parallel notion of "fake pose data".

This is what makes extractor/pipeline.py's analyze_video() testable end to end:
inject MockExtractor() in place of RTMPoseExtractor() and the whole
video -> PoseSequence -> AnalysisResult path runs with no I/O at all.
"""

from __future__ import annotations

from gaitlab import synthetic
from gaitlab.core.schema import PoseSequence

from .base import PoseExtractor


class MockExtractor(PoseExtractor):
    """extract() ignores video_path and returns a synthetic PoseSequence.

    Construction-time kwargs are forwarded to synthetic.generate() (cadence,
    asymmetry, noise, seed, fps, duration, ...), so a test can shape the pose
    without touching a real model — mirroring httpx's MockTransport, which is
    configured once and then satisfies whatever requests a Client sends it.
    """

    def __init__(self, **generate_kwargs):
        self._kwargs = generate_kwargs

    def extract(self, video_path: str, view: str, **_ignored) -> PoseSequence:
        return synthetic.generate(view=view, **self._kwargs)
