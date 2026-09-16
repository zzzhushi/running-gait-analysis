"""Gait-event detection (gaitlab/core/events.py)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from gaitlab.core.events import detect_events


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
#
# detect_events measures the stride period from the ankle-y signal (via
# geometry.dominant_period) and scales its peak-spacing floor to it. These cover the three
# ways that estimate was wrong when it was first written; all three were caught in review,
# and none of them is visible on a clean 170 spm clip.


@pytest.mark.parametrize("cadence", [60, 240])
@pytest.mark.parametrize("fps", [30, 60, 120])
def test_cadence_at_the_advertised_search_limits(synth, cadence, fps):
    """MIN_STRIDE_S/MAX_STRIDE_S advertise an INCLUSIVE 60-240 spm range, so both ends must
    actually work. An interior-only scan for the autocorrelation peak made the exact limits
    unreachable: 60 spm reported as 120 (the search returned nan and fell through), and
    240 spm as 100-120 (it locked onto the two-stride harmonic).
    """
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
    """Frames go missing in bursts, and the surviving timestamps still say when they were.

    This is the browser's normal condition, not a hypothetical: web/js/pose.js learns the
    frame grid from a real-time playthrough and loses frames whenever the compositor is busy.
    Everything else in events.py reads elapsed time via seq.elapsed, so the period estimate
    has to as well — reading an autocorrelation lag in frame INDICES and dividing by one
    average fps assumes uniform spacing, and reported 121 spm for this 172 spm input.

    test_real_timestamps_control_temporal_metrics cannot catch this: scaling every timestamp
    uniformly leaves the samples evenly spaced, which is the assumption being violated here.
    """
    base = _with_timestamps(synth("side-left", fps=120, duration=12, cadence=172, seed=1))
    thinned = _drop_frames(base, keep_one_in, 4.0, 8.0)
    assert thinned.n < base.n, "fixture did not actually drop anything"
    assert detect_events(thinned).cadence_spm == pytest.approx(172, rel=0.05)


def test_robust_period_refuses_a_reference_no_gap_supports():
    """The reference says which observations are plausible; it must not stand in for them.

    Returning the reference when the trim keeps nothing would report a period no detected
    gap is anywhere near — here, 0.50 s (120 spm) from gaps implying about 500 spm.
    """
    from gaitlab.core.events import _robust_period

    assert math.isnan(_robust_period([0.10, 0.12], 0.50))
    # Without a reference the median IS an observation, so that fallback still stands.
    assert _robust_period([0.10, 0.12]) == pytest.approx(0.11)
