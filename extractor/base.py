"""The pose-extraction contract every source implements.

A plain class, not an ABC — matching httpx's BaseTransport rather than Python's
abc module. The base extract() raises NotImplementedError; a subclass only
strictly needs to provide that one method, and nothing here forces it to import
abc or declare @abstractmethod to be a valid extractor.

Three implementations: RTMPoseExtractor (rtmpose.py, the default — sharper foot
keypoints), MediaPipeExtractor (blazepose.py, lighter/install-once), and
MockExtractor (mock.py) — the one that makes the pipeline testable with no
video file and no model download, the same role httpx's MockTransport plays.
"""

from __future__ import annotations

from gaitlab.core.schema import PoseSequence


class PoseExtractor:
    def extract(self, video_path: str, view: str, **kwargs) -> PoseSequence:
        """Run pose extraction on a video and return it as a PoseSequence.

        kwargs vary by source (every / max_seconds / no_ffprobe are common to
        the video-based extractors; RTMPoseExtractor's model/mode are
        constructor args instead, since they configure the instance rather
        than a single call — see rtmpose.py).
        """
        raise NotImplementedError
