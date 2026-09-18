"""Gait-event detection (gaitlab/core/events.py)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from gaitlab.core.events import detect_events
from gaitlab.core.schema import KP_INDEX


def test_cadence_matches_synthetic_input(synth):
    ev = detect_events(synth("side-left", fps=60, duration=6, cadence=172, seed=1))
    assert not math.isnan(ev.cadence_spm)
    assert ev.cadence_spm == pytest.approx(172, rel=0.15)


def test_strikes_detected_each_foot_and_stance_ordered(synth):
    ev = detect_events(synth("side-left", fps=60, duration=6, cadence=170, seed=2))
    assert len(ev.strikes["l"]) >= 4
    assert len(ev.strikes["r"]) >= 4
    for side in ("l", "r"):
        for (s, to) in ev.stance[side]:
            assert to > s                      # toe-off after strike
            assert to - s < ev.strikes[side][-1]  # sane duration


def test_contact_and_stride_times_positive(synth):
    ev = detect_events(synth("side-left", fps=60, duration=6, cadence=176, seed=5))
    for side in ("l", "r"):
        assert ev.contact_time[side] > 0
        assert ev.stride_time[side] > 0
        assert ev.contact_time[side] < ev.stride_time[side]   # contact is part of stride


def test_too_short_clip_returns_empty():
    from gaitlab.core.schema import KEYPOINTS, PoseSequence
    seq = PoseSequence(fps=60, width=100, height=100, view="side-left",
                       frames=[[(0.0, 0.0, 1.0)] * len(KEYPOINTS)] * 3, source="test")
    ev = detect_events(seq)
    assert ev.strikes["l"] == [] and math.isnan(ev.cadence_spm)


def test_faster_cadence_more_strikes(synth):
    slow = detect_events(synth("side-left", fps=60, duration=6, cadence=150, seed=3))
    fast = detect_events(synth("side-left", fps=60, duration=6, cadence=200, seed=3))
    n_slow = len(slow.strikes["l"]) + len(slow.strikes["r"])
    n_fast = len(fast.strikes["l"]) + len(fast.strikes["r"])
    assert n_fast > n_slow


def test_cadence_with_one_fully_occluded_foot(synth):
    """One visible foot supplies stride gaps, each representing two steps."""
    seq = synth("side-left", fps=60, duration=8, cadence=172, seed=1)
    ankle = KP_INDEX["r_ankle"]
    frames = []
    for frame in seq.frames:
        flat = list(frame)
        x, _, confidence = flat[ankle]
        flat[ankle] = (x, float(seq.height - 20), confidence)
        frames.append(flat)

    ev = detect_events(replace(seq, frames=frames))
    assert ev.midstances["r"] == []
    assert ev.midstances["l"]
    assert ev.cadence_spm == pytest.approx(172, rel=0.05)
    assert "r" not in ev.stride_time  # no usable value, not a nan at a present key


def test_real_timestamps_control_temporal_metrics(synth):
    """Nominal FPS must not override the presentation clock on VFR/dropped-frame input."""
    seq = synth("side-left", fps=60, duration=6, cadence=172, seed=7)
    baseline = detect_events(seq)
    scale = 1.2
    timed = replace(seq, timestamps=[i / seq.fps * scale for i in range(seq.n)])
    stretched = detect_events(timed)

    assert stretched.cadence_spm == pytest.approx(baseline.cadence_spm / scale, rel=0.01)
    for side in ("l", "r"):
        assert stretched.stride_time[side] == pytest.approx(
            baseline.stride_time[side] * scale, rel=0.01
        )
        assert stretched.contact_time[side] == pytest.approx(
            baseline.contact_time[side] * scale, rel=0.01
        )


# --------------------------------------------------------------------- period estimation


@pytest.mark.parametrize("cadence", [60, 240])
@pytest.mark.parametrize("fps", [30, 60, 120])
def test_cadence_at_the_advertised_search_limits(synth, cadence, fps):
    ev = detect_events(synth("side-left", fps=fps, duration=8, cadence=cadence, seed=3))
    assert ev.cadence_spm == pytest.approx(cadence, rel=0.05)


def _with_timestamps(seq):
    return replace(seq, timestamps=[i / seq.fps for i in range(seq.n)])


def _drop_frames(seq, keep_one_in, t0, t1):
    """Drop frames inside [t0, t1) while preserving every surviving frame's real timestamp."""
    keep = [i for i in range(seq.n)
            if not (t0 <= seq.timestamps[i] < t1) or i % keep_one_in == 0]
    return replace(seq,
                   frames=[seq.frames[i] for i in keep],
                   timestamps=[seq.timestamps[i] for i in keep])


@pytest.mark.parametrize("keep_one_in", [8, 12])
def test_cadence_survives_frames_dropped_mid_clip(synth, keep_one_in):
    base = _with_timestamps(synth("side-left", fps=120, duration=12, cadence=172, seed=1))
    thinned = _drop_frames(base, keep_one_in, 4.0, 8.0)
    assert thinned.n < base.n, "fixture did not actually drop anything"
    assert detect_events(thinned).cadence_spm == pytest.approx(172, rel=0.05)


def test_robust_period_refuses_a_reference_no_gap_supports():
    from gaitlab.core.events import _robust_period

    assert math.isnan(_robust_period([0.10, 0.12], 0.50))
    # Without a reference the median IS an observation, so that fallback still stands.
    assert _robust_period([0.10, 0.12]) == pytest.approx(0.11)


# ----------------------------------------------------------------- boundary stances


def test_frames_of_interest_anchor_a_middle_stride_not_the_first(synth):
    """The overlay's "View frame" link should land somewhere representative of the
    run, not always ~0.5s in — the first stride of a clip is no more typical than
    any other."""
    from gaitlab.core.events import GaitEvents
    from gaitlab.metrics.compute import compute

    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=1)
    ev = GaitEvents(
        strikes={"l": [10, 50, 90, 130], "r": [30, 70, 110]},
        toeoffs={"l": [20, 60, 100, 140], "r": [40, 80, 120]},
        midstances={"l": [15, 55, 95, 135], "r": [35, 75, 115]},
    )
    foi = compute(seq, events=ev)["frames_of_interest"]
    assert foi["l_strike"] == 90       # midstances[len//2] == midstances[2] == 95 -> same k
    assert foi["l_midstance"] == 95
    assert foi["l_toeoff"] == 100
    assert foi["r_strike"] == 70       # strikes["r"][len//2]


def test_contact_time_excludes_a_final_stance_the_clip_never_saw_lift_off_from(synth):
    """The last stride's forward toe-off search is bounded by the recording's own
    end rather than a real next stride. If it never finds a genuine lift there,
    the clip ended mid-stance and the fallback-window duration is not a
    measurement of how long the foot was actually on the ground."""
    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=4)
    # Cut just past the first stride's midstance, before the foot ever lifts.
    trimmed = replace(seq, frames=seq.frames[:13])
    ev = detect_events(trimmed)
    assert len(ev.stance["l"]) == 1  # confirms the scenario: one, unresolved, stance
    assert "l" not in ev.contact_time
