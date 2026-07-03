"""Per-metric correctness: computed values vs. analytic expectation (not just 'runs').

Uses tiny hand-built poses with known geometry where a metric can be isolated, and
synthetic poses with a known input parameter where the expected output is derivable.
"""

from __future__ import annotations

import math

import pytest

from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab.metrics.compute import compute
from gaitlab.metrics.ctx import _leg_length, knee_flexion_at


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


def test_pelvic_drop_nonnegative_and_worse_side_from_asymmetry(synth):
    # Injected asymmetry deepens the right hip's drop in the synthetic rear generator.
    m = compute(synth("rear", fps=60, duration=6, cadence=170, asymmetry=0.6, seed=7))
    ps = m["per_side"]
    assert ps["l"]["pelvic_drop"] >= 0 and ps["r"]["pelvic_drop"] >= 0
    assert m["values"]["pelvic_drop"] == pytest.approx(max(ps["l"]["pelvic_drop"], ps["r"]["pelvic_drop"]))


def test_overstride_worst_side_is_max(synth):
    m = compute(synth("side-left", fps=60, duration=6, cadence=170, asymmetry=0.3, seed=6))
    ps = m["per_side"]
    assert m["values"]["overstride"] == pytest.approx(max(ps["l"]["overstride"], ps["r"]["overstride"]))


def test_hip_extension_worst_side_is_min(synth):
    m = compute(synth("side-left", fps=60, duration=6, cadence=176, asymmetry=0.3, seed=11))
    ps = m["per_side"]
    assert m["values"]["hip_extension"] == pytest.approx(min(ps["l"]["hip_extension"], ps["r"]["hip_extension"]))
