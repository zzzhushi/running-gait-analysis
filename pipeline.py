"""In-process composition of video extraction and gait analysis.

This root-level module is the only layer that depends on both `extractor` and `gaitlab`,
keeping the analysis engine independent of optional video dependencies. The server and
validation CLI retain subprocess extraction for timeout and process isolation.
"""

from __future__ import annotations

from typing import Optional

from gaitlab.analyze import AnalysisResult, analyze

from extractor.base import PoseExtractor
from extractor.rtmpose import RTMPoseExtractor


def analyze_video(video_path: str, view: str, profile=None, *,
                   extractor: Optional[PoseExtractor] = None,
                   label: str = "", **extract_kwargs) -> AnalysisResult:
    """Extract and analyze a video with an injectable pose source.

    Extra keyword arguments are forwarded to `extractor.extract()`.
    """
    extractor = extractor or RTMPoseExtractor()
    seq = extractor.extract(video_path, view, **extract_kwargs)
    return analyze(seq, label=label or video_path, profile=profile)
