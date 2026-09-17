"""Pose-extraction contract shared by RTMPose, MediaPipe, and synthetic mocks.

Implementations need only override `extract()` and return a `PoseSequence`.
"""

from __future__ import annotations

from gaitlab.core.schema import PoseSequence


class PoseExtractor:
    def extract(self, video_path: str, view: str, **kwargs) -> PoseSequence:
        """Run pose extraction on a video and return it as a PoseSequence.

        Keyword arguments are implementation-specific.
        """
        raise NotImplementedError
