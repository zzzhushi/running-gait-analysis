"""Geometric transforms of a PoseSequence, for invariance tests.

Shared by tests/test_reach.py (hand-built and synthetic poses) and
tests/integration/test_reach_invariants.py (committed real clips), so mirror/swap/scale have
one definition each rather than two that could quietly disagree.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from gaitlab.core.schema import KEYPOINTS, PoseSequence, XY

_LR_SWAP = {}
for _name in KEYPOINTS:
    if _name.startswith("l_"):
        _LR_SWAP[_name] = "r_" + _name[2:]
    elif _name.startswith("r_"):
        _LR_SWAP[_name] = "l_" + _name[2:]


def _map_points(seq: PoseSequence, fn: Callable[[float, float], XY]) -> PoseSequence:
    def moved(point):
        x, y, c = point
        nx, ny = fn(x, y)
        return (nx, ny, c)
    frames = [[moved(p) for p in frame] for frame in seq.frames]
    return replace(seq, frames=frames)


def mirror_image(seq: PoseSequence) -> PoseSequence:
    """Mirror pixel-centre coordinates (`x' = width - 1 - x`); labels unchanged.

    Pair with facing=-1: a horizontally flipped video reverses the apparent direction of
    travel, but a runner's own left foot is still their left foot.
    """
    w = seq.width
    return _map_points(seq, lambda x, y: (w - 1 - x, y))


def swap_sides(seq: PoseSequence) -> PoseSequence:
    """Relabel every l_*/r_* keypoint as its opposite, coordinates unchanged."""
    order = [_LR_SWAP.get(name, name) for name in seq.keypoint_names]
    idx = [seq.keypoint_names.index(name) for name in order]
    frames = [[frame[i] for i in idx] for frame in seq.frames]
    return replace(seq, frames=frames)


def scale(seq: PoseSequence, k: float) -> PoseSequence:
    """Scale coordinates and their image extent together; timestamps are unchanged."""
    if k <= 0:
        raise ValueError("scale factor must be positive")
    scaled = _map_points(seq, lambda x, y: (x * k, y * k))
    return replace(scaled, width=int(round(seq.width * k)), height=int(round(seq.height * k)))


def translate(seq: PoseSequence, dx: float, dy: float) -> PoseSequence:
    return _map_points(seq, lambda x, y: (x + dx, y + dy))


def retime(seq: PoseSequence, k: float) -> PoseSequence:
    """Scale every frame's presentation time by `k`, holding its landmarks fixed.

    Scales `time_at(i)`, not a fresh `i / fps` grid, so a variable-rate or dropped-frame
    clock is stretched rather than replaced by a uniform one.
    """
    return replace(seq, timestamps=[seq.time_at(i) * k for i in range(seq.n)])
