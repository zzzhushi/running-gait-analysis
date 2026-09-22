"""Hip-relative reach curve.

The denominator and facing are injected, so these cover the curve's own arithmetic and
availability rules in isolation from how either is derived.
"""

from __future__ import annotations

import math

import pytest

from gaitlab.core.reach import Denominator, reach_curve
from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab.metrics.ctx import leg_denominator
from tests.pose_transforms import mirror_image, retime, scale, swap_sides, translate

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
    seq = synth("side-left", fps=60, duration=4, cadence=170, seed=1)
    denominator = leg_denominator(seq)
    s = reach_curve(seq, "l", denominator, facing=1)[0]

    assert s.denominator.px == pytest.approx(denominator.px)
    assert s.denominator.method
    assert s.denominator.samples, "the contributing observations are the provenance"
    contributing = s.denominator.samples[0]
    assert contributing.side in ("l", "r")
    assert 0 <= contributing.frame < seq.n
    assert contributing.t == seq.time_at(contributing.frame)
    assert contributing.hip == seq.pt(contributing.frame, f"{contributing.side}_hip")
    assert contributing.knee == seq.pt(contributing.frame, f"{contributing.side}_knee")
    assert contributing.ankle == seq.pt(contributing.frame, f"{contributing.side}_ankle")
    assert contributing.thigh_px == pytest.approx(
        math.dist(contributing.hip[:2], contributing.knee[:2]))
    assert contributing.shank_px == pytest.approx(
        math.dist(contributing.knee[:2], contributing.ankle[:2]))
    assert contributing.total_px == pytest.approx(
        contributing.thigh_px + contributing.shank_px)
    assert contributing.min_confidence == min(
        contributing.hip[2], contributing.knee[2], contributing.ankle[2])


def test_a_structurally_missing_knee_cannot_become_denominator_geometry():
    """An untracked point is the schema's (0,0,0) sentinel, not an image measurement."""
    seq = pose_from_points("side-left", [{
        "l_hip": (300, 500),
        "l_ankle": (320, 600),
    }])
    denominator = leg_denominator(seq)

    assert denominator.samples == ()
    assert denominator.px != denominator.px
    assert denominator.unavailable == "no frames have tracked hip, knee, and ankle landmarks"

    sample = reach_curve(seq, "l", denominator, facing=1)[0]
    assert sample.ankle_reach.px == pytest.approx(20.0)
    assert sample.ankle_reach.pct != sample.ankle_reach.pct
    assert sample.ankle_reach.pct_unavailable == denominator.unavailable


def test_denominator_uses_complete_observations_and_excludes_incomplete_ones():
    seq = pose_from_points("side-left", [
        {"l_hip": (300, 500), "l_ankle": (320, 600)},  # knee absent
        {"l_hip": (300, 500), "l_knee": (300, 550), "l_ankle": (300, 600)},
    ])
    denominator = leg_denominator(seq)

    assert len(denominator.samples) == 1
    assert denominator.samples[0].frame == 1
    assert denominator.px == pytest.approx(100.0)
    assert denominator.unavailable is None


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
    assert {s.side for s in curve} == {"l"}
    assert {s.processing for s in curve} == {"raw"}


# --- invariants --------------------------------------------------------------
#
# Each transform is tested alone. Combining reflection, a facing flip, and a side-label
# swap into one "mirror the clip" case would let two sign errors cancel and still pass.

_RICH_POINTS = {
    "l_hip": (300, 500), "l_ankle": (320, 600),
    "l_heel": (310, 605), "l_big_toe": (340, 605),
}


def test_mirroring_the_image_and_flipping_facing_leaves_reach_unchanged():
    """A horizontally flipped video reverses the apparent direction of travel, but not
    which foot is which; the two must cancel."""
    seq = pose_from_points("side-left", [_RICH_POINTS])
    original = reach_curve(seq, "l", LEG100, facing=1)[0]
    mirrored = reach_curve(mirror_image(seq), "l", LEG100, facing=-1)[0]

    assert mirrored.ankle_reach.pct == pytest.approx(original.ankle_reach.pct)
    assert mirrored.heel_reach.pct == pytest.approx(original.heel_reach.pct)
    assert mirrored.toe_reach.pct == pytest.approx(original.toe_reach.pct)
    assert mirrored.midpoint_reach.pct == pytest.approx(original.midpoint_reach.pct)
    assert mirrored.inclination_deg == pytest.approx(original.inclination_deg)


def test_swapping_left_and_right_labels_swaps_the_sides_reach_values():
    seq = pose_from_points("side-left", [{
        "l_hip": (300, 500), "l_ankle": (320, 600),   # reach = +20
        "r_hip": (340, 500), "r_ankle": (345, 600),   # reach = +5
    }])
    swapped = swap_sides(seq)

    assert reach_curve(seq, "l", LEG100, facing=1)[0].ankle_reach.pct == pytest.approx(20.0)
    assert reach_curve(seq, "r", LEG100, facing=1)[0].ankle_reach.pct == pytest.approx(5.0)
    assert reach_curve(swapped, "l", LEG100, facing=1)[0].ankle_reach.pct == pytest.approx(5.0)
    assert reach_curve(swapped, "r", LEG100, facing=1)[0].ankle_reach.pct == pytest.approx(20.0)


def test_scaling_every_coordinate_leaves_the_percentage_unchanged():
    """A denominator derived from the same pose scales with it, so the ratio survives even
    though the pixel offset does not."""
    seq = pose_from_points("side-left", [{
        "l_hip": (300, 500), "l_knee": (300, 550), "l_ankle": (320, 600),
    }])
    scaled = scale(seq, 3.0)
    original = reach_curve(seq, "l", leg_denominator(seq), facing=1)[0]
    grown = reach_curve(scaled, "l", leg_denominator(scaled), facing=1)[0]

    assert grown.ankle_reach.px == pytest.approx(original.ankle_reach.px * 3.0)
    assert grown.ankle_reach.pct == pytest.approx(original.ankle_reach.pct)
    assert grown.inclination_deg == pytest.approx(original.inclination_deg)


def test_translating_every_coordinate_leaves_reach_unchanged():
    """Reach is a difference between two points, so a shared offset cancels regardless of
    the denominator."""
    seq = pose_from_points("side-left", [_RICH_POINTS])
    moved = translate(seq, dx=1000.0, dy=-2000.0)
    original = reach_curve(seq, "l", LEG100, facing=1)[0]
    shifted = reach_curve(moved, "l", LEG100, facing=1)[0]

    assert shifted.ankle_reach.px == pytest.approx(original.ankle_reach.px)
    assert shifted.ankle_reach.pct == pytest.approx(original.ankle_reach.pct)
    assert shifted.midpoint_reach.pct == pytest.approx(original.midpoint_reach.pct)
    assert shifted.inclination_deg == pytest.approx(original.inclination_deg)


def test_reach_does_not_depend_on_timestamps(synth):
    """Overstride is not a timing metric: only detecting *which* frame is a strike depends
    on timestamps, not the reach curve's value at a given frame."""
    seq = synth("side-left", fps=60, duration=3, cadence=170, seed=2)
    stretched = retime(seq, k=1.7)

    original = reach_curve(seq, "l", LEG100, facing=1)
    retimed = reach_curve(stretched, "l", LEG100, facing=1)

    assert [s.t for s in original] != [s.t for s in retimed]
    for o, r in zip(original, retimed):
        assert r.ankle_reach.px == o.ankle_reach.px
        assert r.ankle_reach.pct == o.ankle_reach.pct
        assert r.inclination_deg == o.inclination_deg
