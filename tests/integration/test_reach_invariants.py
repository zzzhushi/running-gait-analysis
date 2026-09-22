"""Reach-curve invariants (tests/test_reach.py) on committed real clips, not just hand poses.

Each committed clip's own detected strikes are the fixed reference frames; a mirrored, scaled,
or translated clip is compared to the original only at those indices, so a transform's effect
on event detection cannot leak into what this module is checking.
"""

from __future__ import annotations

import json

import pytest

from gaitlab.core import reach as reach_mod
from gaitlab.core.events import detect_events
from gaitlab.core.schema import PoseSequence
from gaitlab.metrics.ctx import leg_denominator
from tests.integration.clipcase import load_clips
from tests.pose_transforms import mirror_image, scale, swap_sides, translate

CLIPS = [c for c in load_clips(extractors=("rtmpose",))
         if PoseSequence.from_pose_dict(json.loads(c.pose_path.read_text())).is_side()]


def _ids(clip):
    return clip.id


@pytest.fixture(scope="module", params=CLIPS, ids=_ids)
def clip_seq(request):
    clip = request.param
    seq = PoseSequence.from_pose_dict(json.loads(clip.pose_path.read_text())).validate()
    strikes = detect_events(seq).strikes
    for side in ("l", "r"):
        # Every test below loops over strikes[side]; an empty list would pass vacuously
        # rather than say the fixture no longer exercises the formula.
        assert strikes[side], f"{clip.id}: no detected {side} strikes"
    return seq, strikes


def test_mirroring_leaves_reach_unchanged_at_the_original_strike_frames(clip_seq):
    seq, strikes = clip_seq
    mirrored = mirror_image(seq)
    for side in ("l", "r"):
        original = reach_mod.reach_curve(seq, side, leg_denominator(seq), seq.facing_sign())
        flipped = reach_mod.reach_curve(mirrored, side, leg_denominator(mirrored), mirrored.facing_sign())
        for f in strikes[side]:
            assert flipped[f].ankle_reach.pct == pytest.approx(original[f].ankle_reach.pct, abs=1e-6)
            assert flipped[f].inclination_deg == pytest.approx(original[f].inclination_deg, abs=1e-6)


def test_swapping_sides_swaps_reach_at_the_original_strike_frames(clip_seq):
    """facing_sign() reads the left foot only, so it is not itself swap-invariant (a
    separate, open question); this test holds facing fixed to isolate the curve's own
    swap behavior from that."""
    seq, strikes = clip_seq
    swapped = swap_sides(seq)
    facing = seq.facing_sign()
    denominator = leg_denominator(seq)  # pooled over both sides, so unaffected by the swap

    for side, other in (("l", "r"), ("r", "l")):
        original = reach_mod.reach_curve(seq, side, denominator, facing)
        after_swap = reach_mod.reach_curve(swapped, other, denominator, facing)
        for f in strikes[side]:
            assert after_swap[f].ankle_reach.pct == pytest.approx(original[f].ankle_reach.pct, abs=1e-6)


def test_scaling_leaves_the_percentage_unchanged_at_the_original_strike_frames(clip_seq):
    seq, strikes = clip_seq
    scaled = scale(seq, 2.0)
    for side in ("l", "r"):
        original = reach_mod.reach_curve(seq, side, leg_denominator(seq), seq.facing_sign())
        grown = reach_mod.reach_curve(scaled, side, leg_denominator(scaled), scaled.facing_sign())
        for f in strikes[side]:
            assert grown[f].ankle_reach.pct == pytest.approx(original[f].ankle_reach.pct, rel=1e-6)


def test_translating_leaves_reach_unchanged_at_the_original_strike_frames(clip_seq):
    seq, strikes = clip_seq
    moved = translate(seq, dx=500.0, dy=-300.0)
    for side in ("l", "r"):
        original = reach_mod.reach_curve(seq, side, leg_denominator(seq), seq.facing_sign())
        shifted = reach_mod.reach_curve(moved, side, leg_denominator(moved), moved.facing_sign())
        for f in strikes[side]:
            assert shifted[f].ankle_reach.pct == pytest.approx(original[f].ankle_reach.pct, abs=1e-6)
