"""Hip-relative reach curve (gaitlab/core/reach.py).

The denominator and facing are injected rather than derived, so these tests check the curve's
own arithmetic in isolation from _leg_length and facing_sign -- see docs/metrics/overstride.md
for why the denominator itself is still an open decision.
"""

from __future__ import annotations

import math

import pytest

from gaitlab.core.reach import reach_curve
from gaitlab.core.schema import KEYPOINTS, PoseSequence


def pose_from_points(view, frames, fps=60, width=1080, height=1920):
    """Build a PoseSequence from [{keypoint_name: (x, y)}, ...] (conf 1.0; others absent)."""
    F = []
    for fp in frames:
        fr = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        for name, (x, y) in fp.items():
            fr[KEYPOINTS.index(name)] = (float(x), float(y), 1.0)
        F.append(fr)
    return PoseSequence(fps=fps, width=width, height=height, view=view, frames=F, source="test")


def test_ankle_reach_is_exact_on_hand_computed_coordinates():
    # hip at x=300, ankle 20px ahead in image x; denominator injected as exactly 100.
    seq = pose_from_points("side-left", [{"l_hip": (300, 500), "l_ankle": (320, 600)}])
    curve = reach_curve(seq, "l", denominator_px=100.0, facing=1)
    assert len(curve) == 1
    s = curve[0]
    assert s.ankle_reach_px == pytest.approx(20.0)
    assert s.ankle_reach_pct == pytest.approx(20.0)
    assert s.valid


def test_reach_behind_the_hip_is_negative():
    seq = pose_from_points("side-left", [{"l_hip": (300, 500), "l_ankle": (295, 600)}])
    curve = reach_curve(seq, "l", denominator_px=100.0, facing=1)
    assert curve[0].ankle_reach_pct == pytest.approx(-5.0)


def test_facing_flips_the_sign_not_the_magnitude():
    seq = pose_from_points("side-left", [{"l_hip": (300, 500), "l_ankle": (320, 600)}])
    fwd = reach_curve(seq, "l", denominator_px=100.0, facing=1)[0]
    rev = reach_curve(seq, "l", denominator_px=100.0, facing=-1)[0]
    assert rev.ankle_reach_pct == pytest.approx(-fwd.ankle_reach_pct)


def test_inclination_matches_the_contract_formula():
    # ankle 20px ahead, 100px below the hip -> atan2(20, 100).
    seq = pose_from_points("side-left", [{"l_hip": (300, 500), "l_ankle": (320, 600)}])
    s = reach_curve(seq, "l", denominator_px=100.0, facing=1)[0]
    assert s.inclination_deg == pytest.approx(math.degrees(math.atan2(20, 100)))


def test_heel_toe_and_midpoint_are_reported_alongside_ankle():
    seq = pose_from_points("side-left", [{
        "l_hip": (300, 500), "l_ankle": (320, 600),
        "l_heel": (310, 605), "l_big_toe": (340, 605),
    }])
    s = reach_curve(seq, "l", denominator_px=100.0, facing=1)[0]
    assert s.heel_reach_px == pytest.approx(10.0)
    assert s.toe_reach_px == pytest.approx(40.0)
    assert s.midpoint_reach_px == pytest.approx(25.0)  # midpoint of heel/toe x, minus hip x
    assert s.foot_midpoint_proxy == pytest.approx((325.0, 605.0))


def test_missing_ankle_is_invalid_not_a_zero_coordinate():
    seq = pose_from_points("side-left", [{"l_hip": (300, 500)}])  # ankle never set -> (0,0,0)
    s = reach_curve(seq, "l", denominator_px=100.0, facing=1)[0]
    assert not s.valid
    assert s.invalid_reason == "hip or ankle not tracked this frame"
    assert s.ankle_reach_pct != s.ankle_reach_pct  # NaN, not a garbage number from (0,0,0)


def test_missing_heel_or_toe_does_not_invalidate_the_ankle_sample():
    seq = pose_from_points("side-left", [{"l_hip": (300, 500), "l_ankle": (320, 600)}])
    s = reach_curve(seq, "l", denominator_px=100.0, facing=1)[0]
    assert s.valid
    assert s.heel_reach_px != s.heel_reach_px  # NaN
    assert s.midpoint_reach_px != s.midpoint_reach_px  # needs both heel and toe


@pytest.mark.parametrize("bad_denominator", [float("nan"), 0.0, -5.0])
def test_bad_denominator_invalidates_normalized_values_but_keeps_pixels(bad_denominator):
    seq = pose_from_points("side-left", [{"l_hip": (300, 500), "l_ankle": (320, 600)}])
    s = reach_curve(seq, "l", denominator_px=bad_denominator, facing=1)[0]
    assert not s.valid
    assert s.invalid_reason == "denominator unavailable (NaN or non-positive)"
    assert s.ankle_reach_px == pytest.approx(20.0)  # pixels don't depend on the denominator
    assert s.ankle_reach_pct != s.ankle_reach_pct  # NaN


def test_one_sample_per_frame_retrievable_without_a_full_report(synth):
    seq = synth("side-left", fps=60, duration=4, cadence=170, seed=1)
    curve = reach_curve(seq, "l", denominator_px=100.0, facing=1)
    assert len(curve) == seq.n
    assert [s.frame for s in curve] == list(range(seq.n))
    assert [s.t for s in curve] == [seq.time_at(f) for f in range(seq.n)]
