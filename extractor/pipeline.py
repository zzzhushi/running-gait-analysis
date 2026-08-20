"""video -> PoseSequence -> AnalysisResult.

The step server.py and validate_run.py each currently duplicate by hand: spawn
extract_pose.py as a subprocess, load the JSON it writes, then call
gaitlab.analyze(). analyze_video() is the in-process equivalent, built on the
PoseExtractor seam so the source is swappable — #34 needs exactly that, to run
one clip through RTMPoseExtractor and MediaPipeExtractor and compare.

Lives here, not in gaitlab/, on purpose: gaitlab/ is pure Python, stdlib only,
and importing an extractor into it would put a pip-installable dependency
behind an import gaitlab.py never had before. extractor/ already depends on
gaitlab/ (every extractor imports gaitlab.core.schema); this keeps that
direction one-way.

Deliberately NOT wired into server.py or validate_run.py here: both extract via
subprocess today, which gives that step process isolation and a hard timeout
(server.py's INGEST_TIMEOUT = 600s) that calling extract() in-process does not
replicate — a hang or a memory leak in rtmlib would take the caller down with
it instead of just failing one request. Swapping either over is a separate,
larger decision than adding the seam.
"""

from __future__ import annotations

from typing import Optional

from gaitlab.analyze import AnalysisResult, analyze

from .base import PoseExtractor
from .rtmpose import RTMPoseExtractor


def analyze_video(video_path: str, view: str, profile=None, *,
                   extractor: Optional[PoseExtractor] = None,
                   label: str = "", **extract_kwargs) -> AnalysisResult:
    """Extract and analyze in one call. extractor defaults to RTMPoseExtractor;
    pass MockExtractor() (or any PoseExtractor) to swap the source — that's the
    whole reason this takes an extractor instead of hardcoding one.

    extract_kwargs (every / max_seconds / no_ffprobe) are forwarded to
    extractor.extract(). profile may be a RunnerProfile or the wire dict —
    analyze() already accepts either.
    """
    extractor = extractor or RTMPoseExtractor()
    seq = extractor.extract(video_path, view, **extract_kwargs)
    return analyze(seq, label=label or video_path, profile=profile)
