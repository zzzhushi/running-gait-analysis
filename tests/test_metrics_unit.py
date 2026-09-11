"""Per-metric correctness: computed values vs. analytic expectation (not just 'runs').

Uses tiny hand-built poses with known geometry where a metric can be isolated, and
synthetic poses with a known input parameter where the expected output is derivable.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from gaitlab.core.events import GaitEvents
from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab.metrics.compute import compute
from gaitlab.metrics.ctx import Ctx, _leg_length, knee_flexion_at
from gaitlab.metrics.defs import METRIC_DEFS
from gaitlab.metrics.keys import MetricKey


def pose_from_points(view, frames, fps=60, width=1080, height=1920):
    """Build a PoseSequence from [{keypoint_name: (x, y)}, ...] (conf 1.0; others absent)."""
    F = []
    for fp in frames:
        fr = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        fr = list(fr)
        for name, (x, y) in fp.items():
            fr[KEYPOINTS.index(name)] = (float(x), float(y), 1.0)
        F.append(fr)
    return PoseSequence(fps=fps, width=width, height=height, view=view, frames=F, source="test")


# --- analytic: isolated formulas ------------------------------------------

@pytest.mark.parametrize("hip,knee,ankle,expected", [
    ((0, 0), (0, 100), (100, 100), 90.0),    # right angle at knee -> 90 deg flexion
    ((0, 0), (0, 100), (0, 200), 0.0),       # straight leg -> 0 deg flexion
    # knee->hip = (0,-1); knee->ankle at 150 deg interior => 30 deg flexion
    ((0, 0), (0, 100), (100 * math.sin(math.radians(150)), 100 - 100 * math.cos(math.radians(150))), 30.0),
])
def test_knee_flexion_analytic(hip, knee, ankle, expected):
    seq = pose_from_points("side-left", [{"l_hip": hip, "l_knee": knee, "l_ankle": ankle}])
    assert knee_flexion_at(seq, 0, "l") == pytest.approx(expected, abs=0.5)


def test_leg_length_is_sum_of_thigh_and_shank():
    seq = pose_from_points("side-left", [{"l_hip": (0, 0), "l_knee": (0, 100), "l_ankle": (100, 100)}])
    # 100 (hip->knee) + 100 (knee->ankle)
    assert _leg_length(seq) == pytest.approx(200.0, abs=1e-6)


def test_leg_length_has_finite_fallback_when_landmarks_are_missing():
    assert _leg_length(pose_from_points("side-left", [{}])) == 1.0


# --- analytic-from-parameter: synthetic input we control -------------------

def test_trunk_lean_recovers_synthetic_8deg(synth):
    # synthetic.py builds the torso at a fixed 8.0 deg forward lean.
    m = compute(synth("side-left", fps=60, duration=5, cadence=176, seed=4))
    assert m["values"]["trunk_lean"] == pytest.approx(8.0, abs=1.5)


def test_vertical_oscillation_matches_synthetic_amplitude(synth):
    # synthetic: hip_y peak-to-peak = 2 * 0.028H; leg = thigh+shank = 0.49H.
    # => VO% = 2*0.028/0.49 * 100 ≈ 11.4 %leg
    m = compute(synth("side-left", fps=60, duration=6, cadence=176, seed=5))
    assert m["values"]["vertical_oscillation"] == pytest.approx(11.4, abs=2.0)


def test_pelvic_drop_preserves_signed_swing_side_direction(synth):
    m = compute(synth("rear", fps=60, duration=6, cadence=170, asymmetry=0.6, seed=7))
    ps = m["per_side"]
    assert all(math.isfinite(ps[side]["pelvic_drop"]) for side in ("l", "r"))
    assert m["values"]["pelvic_drop"] == pytest.approx((ps["l"]["pelvic_drop"] + ps["r"]["pelvic_drop"]) / 2)


def test_overstride_worst_side_is_max(synth):
    m = compute(synth("side-left", fps=60, duration=6, cadence=170, asymmetry=0.3, seed=6))
    ps = m["per_side"]
    assert m["values"]["overstride"] == pytest.approx(max(ps["l"]["overstride"], ps["r"]["overstride"]))


def test_uncalibrated_contact_metrics_are_descriptive_only():
    """A provisional event anchor must not drive the score or coaching contract."""
    for key in (MetricKey.CONTACT_TIME, MetricKey.DUTY_FACTOR):
        defn = METRIC_DEFS[key]
        assert defn.scored is False
        assert defn.confidence == "low"
        assert defn.card_status == "info"
        assert defn.trigger(999.0, {}, METRIC_DEFS) is None

    assert METRIC_DEFS[MetricKey.CONTACT_TIME_MS].per_side is False


def test_step_length_uses_real_timestamps(synth):
    seq = synth("side-left", fps=60, duration=6, cadence=172, seed=8)
    baseline = compute(seq, calibration={"speed_kmh": 12.0})
    timed = replace(seq, timestamps=[i / seq.fps * 1.2 for i in range(seq.n)])
    stretched = compute(timed, calibration={"speed_kmh": 12.0})

    for side in ("l", "r"):
        assert stretched["per_side"][side]["step_length"] == pytest.approx(
            baseline["per_side"][side]["step_length"] * 1.2, rel=0.01
        )


def test_hip_extension_worst_side_is_min(synth):
    m = compute(synth("side-left", fps=60, duration=6, cadence=176, asymmetry=0.3, seed=11))
    ps = m["per_side"]
    assert m["values"]["hip_extension"] == pytest.approx(min(ps["l"]["hip_extension"], ps["r"]["hip_extension"]))


# --- crossover detection: must ignore single noisy frames -------------------

def _rear_ankles(pairs):
    """Rear pose, one frame per (l_ankle_x, r_ankle_x). Midline at x=500, leg ≈ 200 px."""
    frames = [{
        "mid_hip": (500, 0),
        "l_hip": (480, 0), "l_knee": (480, 100), "l_ankle": (lx, 200),
        "r_hip": (520, 0), "r_knee": (520, 100), "r_ankle": (rx, 200),
    } for lx, rx in pairs]
    return pose_from_points("rear", frames)


def _crossover(seq, strikes):
    ev = GaitEvents()
    ev.strikes = strikes
    return Ctx(seq, ev, None).step_width_and_crossover()[1]


def _mirror(seq):
    frames = [[(seq.width - x, y, conf) for x, y, conf in frame] for frame in seq.frames]
    return PoseSequence(
        fps=seq.fps, width=seq.width, height=seq.height, view=seq.view,
        frames=frames, source=f"{seq.source}-mirrored", timestamps=seq.timestamps,
    )


def test_crossover_ignores_single_midline_touch():
    # Three clean straddling strikes + one where the left ankle lands ~0.5% past the
    # midline (noise). The old `> 0` test flagged crossover here; it must not now.
    seq = _rear_ankles([(470, 530), (470, 530), (470, 530), (501, 530)])
    assert _crossover(seq, {"l": [1, 3], "r": [0, 2]}) is False


def test_crossover_flags_persistent_crossing():
    # Successive right placements are left of successive left placements by >3% leg.
    seq = _rear_ankles([(535, 515), (535, 515), (535, 515), (535, 515)])
    assert _crossover(seq, {"l": [1, 3], "r": [0, 2]}) is True


@pytest.mark.parametrize("pairs, expected", [
    ([(470, 530)] * 4, False),
    ([(535, 515)] * 4, True),
])
def test_step_width_and_crossover_are_mirror_invariant(pairs, expected):
    seq = _rear_ankles(pairs)
    strikes = {"l": [1, 3], "r": [0, 2]}
    ev = GaitEvents()
    ev.strikes = strikes
    original = Ctx(seq, ev, None).step_width_and_crossover()
    mirrored = Ctx(_mirror(seq), ev, None).step_width_and_crossover()
    assert original[0] == pytest.approx(mirrored[0])
    assert original[1] is expected
    assert mirrored[1] is expected


def test_frontal_plane_angles_are_mirror_invariant():
    points = {
        "l_hip": (470, 100), "r_hip": (530, 110),
        "l_shoulder": (465, 20), "r_shoulder": (535, 12),
    }
    seq = pose_from_points("rear", [points] * 5)
    ev = GaitEvents()
    original = Ctx(seq, ev, None)
    mirrored = Ctx(_mirror(seq), ev, None)
    assert original.pelvic_tilt_series() == pytest.approx(mirrored.pelvic_tilt_series())
    assert original.shoulder_angle_series() == pytest.approx(mirrored.shoulder_angle_series())


@pytest.mark.parametrize("wrists, expected", [
    (((460, 50), (540, 50)), False),
    (((510, 50), (490, 50)), True),
])
def test_arm_crossover_is_mirror_invariant(wrists, expected):
    points = {
        "mid_hip": (500, 100), "l_hip": (470, 100), "r_hip": (530, 100),
        "l_wrist": wrists[0], "r_wrist": wrists[1],
    }
    seq = pose_from_points("rear", [points] * 5)
    definition = METRIC_DEFS[MetricKey.ARM_CROSSOVER]
    original = definition.compute(Ctx(seq, GaitEvents(), None), None)
    mirrored_seq = _mirror(seq)
    mirrored = definition.compute(Ctx(mirrored_seq, GaitEvents(), None), None)
    assert original is expected
    assert mirrored is expected
