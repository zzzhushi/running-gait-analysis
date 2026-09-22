"""tests/pose_transforms.py: each transform on a single known point.

These are shared by every invariant test in test_reach.py and test_reach_invariants.py, so a
bug here would silently invalidate several tests that each look correct on their own.
"""

from __future__ import annotations

import pytest

from gaitlab.core.schema import KEYPOINTS, PoseSequence
from tests.pose_transforms import mirror_image, retime, scale, swap_sides, translate


def _seq(**points):
    fr = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
    for name, (x, y) in points.items():
        fr[KEYPOINTS.index(name)] = (float(x), float(y), 1.0)
    return PoseSequence(fps=60, width=1000, height=2000, view="side-left", frames=[fr], source="test")


def test_mirror_image_reflects_x_about_the_frame_width():
    seq = _seq(l_hip=(300, 500))
    mirrored = mirror_image(seq)
    assert mirrored.xy(0, "l_hip") == pytest.approx((700.0, 500.0))  # width=1000


def test_swap_sides_moves_each_side_to_its_opposite_label():
    seq = _seq(l_hip=(300, 500), r_hip=(700, 500))
    swapped = swap_sides(seq)
    assert swapped.xy(0, "l_hip") == pytest.approx((700.0, 500.0))
    assert swapped.xy(0, "r_hip") == pytest.approx((300.0, 500.0))


def test_swap_sides_leaves_the_midline_unchanged():
    seq = _seq(mid_hip=(500, 500))
    assert swap_sides(seq).xy(0, "mid_hip") == pytest.approx((500.0, 500.0))


def test_scale_multiplies_every_coordinate():
    seq = _seq(l_hip=(300, 500))
    assert scale(seq, 2.0).xy(0, "l_hip") == pytest.approx((600.0, 1000.0))


def test_translate_adds_the_same_offset_to_every_point():
    seq = _seq(l_hip=(300, 500))
    assert translate(seq, dx=10, dy=-20).xy(0, "l_hip") == pytest.approx((310.0, 480.0))


def test_retime_scales_actual_spacing_not_a_fresh_uniform_grid():
    """A variable-rate clip's gaps must scale with it, not be replaced by fps-derived ones."""
    seq = PoseSequence(
        fps=60, width=1000, height=2000, view="side-left", source="test",
        frames=[[(0.0, 0.0, 0.0)] * len(KEYPOINTS) for _ in range(4)],
        timestamps=[0.0, 0.01, 0.05, 0.06],  # deliberately uneven: not i/fps
    )
    stretched = retime(seq, 3.0)
    assert stretched.timestamps == pytest.approx([0.0, 0.03, 0.15, 0.18])
