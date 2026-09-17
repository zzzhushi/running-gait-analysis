"""Synthetic PoseExtractor for testing the full pipeline without video or a model.

Wraps `gaitlab.synthetic.generate()` so mock and direct synthetic inputs share one schema.
"""

from __future__ import annotations

from gaitlab import synthetic
from gaitlab.core.schema import PoseSequence

from .base import PoseExtractor


class MockExtractor(PoseExtractor):
    """Return a synthetic PoseSequence, ignoring the video path.

    Construction arguments are forwarded to `synthetic.generate()`.
    """

    def __init__(self, **generate_kwargs):
        self._kwargs = generate_kwargs

    def extract(self, video_path: str, view: str, **_ignored) -> PoseSequence:
        return synthetic.generate(view=view, **self._kwargs)
