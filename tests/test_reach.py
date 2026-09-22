"""Hip-relative reach curve (gaitlab/core/reach.py).

The denominator and facing are injected rather than derived, so these tests check the curve's
own arithmetic in isolation from leg_denominator and facing_sign -- see
docs/metrics/overstride.md for why the denominator itself is still an open decision.
"""

from __future__ import annotations

import math

import pytest

from gaitlab.core.reach import Denominator, reach_curve
from gaitlab.core.schema import KEYPOINTS, PoseSequence

LEG100 = Denominator.injected(100.0)


def pose_from_points(view, frames, fps=60, width=1080, height=1920):
    """Build a PoseSequence from [{keypoint_name: (x, y)}, ...] (conf 1.0; others absent)."""
    F = []
    for fp in frames:
        fr = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        for name, (x, y) in fp.items():
            fr[KEYPOINTS.index(name)] = (float(x), float(y), 1.0)
        F.append(fr)
    return PoseSequence(fps=fps, width=width, height=height, view=view, frames=F, source="test")


def one(points, denominator=LEG100, facing=1):
    return reach_curve(pose_from_points("side-left", [points]), "l", denominator, facing)[0]


# --- arithmetic ------------------------------------------------------------

def test_ankle_reach_is_exact_on_hand_computed_coordinates():
    # hip at x=300, ankle 20px ahead in image x; denominator injected as exactly 100.
    s = one({"l_hip": (300, 500), "l_ankle": (320, 600)})
    assert s.ankle_reach.px == pytest.approx(20.0)
    assert s.ankle_reach.pct == pytest.approx(20.0)
    assert s.ankle_reach.available


def test_reach_behind_the_hip_is_negative():
    assert one({"l_hip": (300, 500), "l_ankle": (295, 600)}).ankle_reach.pct == pytest.approx(-5.0)


def test_facing_flips_the_sign_not_the_magnitude():
    pts = {"l_hip": (300, 500), "l_ankle": (320, 600)}
    assert one(pts, facing=-1).ankle_reach.pct == pytest.approx(-one(pts).ankle_reach.pct)


def test_inclination_matches_the_contract_formula():
    # ankle 20px ahead, 100px below the hip -> atan2(20, 100).
    s = one({"l_hip": (300, 500), "l_ankle": (320, 600)})
    assert s.inclination_deg == pytest.approx(math.degrees(math.atan2(20, 100)))
    assert s.inclination_unavailable is None


def test_heel_toe_and_midpoint_are_reported_alongside_ankle():
    s = one({"l_hip": (300, 500), "l_ankle": (320, 600),
             "l_heel": (310, 605), "l_big_toe": (340, 605)})
    assert s.heel_reach.px == pytest.approx(10.0)
    assert s.toe_reach.px == pytest.approx(40.0)
    assert s.midpoint_reach.px == pytest.approx(25.0)
    assert s.foot_midpoint_proxy == pytest.approx((325.0, 605.0))


# --- per-candidate availability -------------------------------------------

def test_a_missing_ankle_does_not_erase_heel_toe_or_midpoint():
    """Each candidate needs only its own landmarks.

    The candidates exist to be compared against each other, so withholding heel/toe/midpoint
    because a different landmark is missing would defeat the artifact's purpose.
    """
    s = one({"l_hip": (300, 500), "l_heel": (310, 605), "l_big_toe": (340, 605)})

    assert s.ankle_reach.px_unavailable == "ankle not tracked this frame"
    assert s.inclination_unavailable == "ankle not tracked this frame"

    assert s.heel_reach.px == pytest.approx(10.0)
    assert s.toe_reach.px == pytest.approx(40.0)
    assert s.midpoint_reach.px == pytest.approx(25.0)
    assert s.foot_midpoint_proxy == pytest.approx((325.0, 605.0))
    assert s.heel_reach.available and s.toe_reach.available and s.midpoint_reach.available


def test_a_missing_hip_takes_every_candidate_with_it():
    """The hip is the shared reference, so it is the one landmark all candidates need."""
    s = one({"l_ankle": (320, 600), "l_heel": (310, 605), "l_big_toe": (340, 605)})
    for reading in (s.ankle_reach, s.heel_reach, s.toe_reach, s.midpoint_reach):
        assert reading.px_unavailable == "hip not tracked this frame"
        assert reading.px != reading.px  # NaN, not a garbage offset from an unset (0,0,0)


def test_midpoint_needs_both_heel_and_toe():
    s = one({"l_hip": (300, 500), "l_ankle": (320, 600), "l_heel": (310, 605)})
    assert s.heel_reach.available
    assert s.midpoint_reach.px_unavailable == "big toe not tracked this frame"
    assert s.toe_reach.px_unavailable == "big toe not tracked this frame"


def test_every_unavailable_measurement_states_a_reason():
    s = one({"l_hip": (300, 500)})
    for reading in (s.ankle_reach, s.heel_reach, s.toe_reach, s.midpoint_reach):
        assert reading.px != reading.px
        assert reading.px_unavailable, "a NaN with no reason is not diagnostic"


# --- denominator -----------------------------------------------------------

@pytest.mark.parametrize("bad_px,reason", [
    (float("nan"), "denominator is NaN"),
    (0.0, "denominator is not positive"),
    (-5.0, "denominator is not positive"),
])
def test_a_bad_denominator_invalidates_percentages_but_not_pixels(bad_px, reason):
    """Pixel offsets do not depend on the denominator, so they survive it being unusable."""
    s = one({"l_hip": (300, 500), "l_ankle": (320, 600)}, denominator=Denominator.injected(bad_px))
    assert s.ankle_reach.px == pytest.approx(20.0)
    assert s.ankle_reach.px_unavailable is None
    assert s.ankle_reach.pct != s.ankle_reach.pct  # NaN
    assert s.ankle_reach.pct_unavailable == reason
    assert s.inclination_deg == pytest.approx(math.degrees(math.atan2(20, 100)))


def test_the_curve_carries_the_denominator_and_its_provenance(synth):
    """A suspicious percentage must be traceable to the observations behind its denominator."""
    from gaitlab.metrics.ctx import leg_denominator

    seq = synth("side-left", fps=60, duration=4, cadence=170, seed=1)
    denominator = leg_denominator(seq)
    s = reach_curve(seq, "l", denominator, facing=1)[0]

    assert s.denominator.px == pytest.approx(denominator.px)
    assert s.denominator.method
    assert s.denominator.samples, "the contributing observations are the provenance"
    contributing = s.denominator.samples[0]
    assert contributing.side in ("l", "r")
    assert 0 <= contributing.frame < seq.n
    assert contributing.total_px == pytest.approx(contributing.thigh_px + contributing.shank_px)


def test_injected_denominators_declare_that_they_have_no_provenance():
    assert LEG100.samples == ()
    assert LEG100.method == "injected"
    assert LEG100.unavailable is None


# --- shape -----------------------------------------------------------------

def test_one_sample_per_frame_retrievable_without_a_full_report(synth):
    seq = synth("side-left", fps=60, duration=4, cadence=170, seed=1)
    curve = reach_curve(seq, "l", LEG100, facing=1)
    assert len(curve) == seq.n
    assert [s.frame for s in curve] == list(range(seq.n))
    assert [s.t for s in curve] == [seq.time_at(f) for f in range(seq.n)]
