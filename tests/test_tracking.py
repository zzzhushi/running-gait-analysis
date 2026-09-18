"""Per-frame tracking trust (gaitlab/core/tracking.py).

A tracker can report high confidence for a landmark it has assigned to the
wrong body part — e.g. swapping the near and far leg during an occlusion —
so confidence alone cannot catch every mistracked frame. These tests cover
both failure modes: reported low confidence, and confidently-wrong geometry.
"""

from __future__ import annotations

from dataclasses import replace

from gaitlab.core.schema import KP_INDEX
from gaitlab.core.tracking import leg_trust


def test_trusts_a_clean_synthetic_clip(synth):
    seq = synth("side-left", fps=60, duration=4, cadence=170, seed=1)
    trust = leg_trust(seq, "l")
    assert len(trust) == seq.n
    assert sum(trust) / len(trust) > 0.95


def test_flags_a_low_confidence_span(synth):
    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=2)
    ankle = KP_INDEX["l_ankle"]
    lo, hi = seq.n // 2, seq.n // 2 + 20
    frames = list(seq.frames)
    for i in range(lo, hi):
        x, y, _ = frames[i][ankle]
        flat = list(frames[i])
        flat[ankle] = (x, y, 0.1)  # reported, but too low to trust
        frames[i] = flat
    trust = leg_trust(replace(seq, frames=frames), "l")
    assert not any(trust[lo:hi])
    assert all(trust[:lo])


def test_flags_an_implausible_segment_length_despite_high_confidence(synth):
    """A confidently-reported landmark that breaks the clip's own limb-length
    scale (e.g. a near/far leg swap) must not be trusted just because its
    confidence score is high."""
    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=3)
    knee, ankle = KP_INDEX["l_knee"], KP_INDEX["l_ankle"]
    lo, hi = seq.n // 2, seq.n // 2 + 15
    frames = list(seq.frames)
    for i in range(lo, hi):
        kx, ky, _ = frames[i][knee]
        _, _, c = frames[i][ankle]
        flat = list(frames[i])
        flat[ankle] = (kx + 10.0, ky + 10.0, c)  # same confidence, foot pinned at the knee
        frames[i] = flat
    trust = leg_trust(replace(seq, frames=frames), "l")
    assert not any(trust[lo:hi])


def test_too_few_confident_frames_skips_segment_check_gracefully():
    from gaitlab.core.schema import KEYPOINTS, PoseSequence
    seq = PoseSequence(fps=30, width=200, height=400, view="side-left",
                        frames=[[(0.0, 0.0, 0.0)] * len(KEYPOINTS)] * 5, source="test")
    # Should not raise even though there is no confident data to derive a median from.
    assert leg_trust(seq, "l") == [False] * 5
