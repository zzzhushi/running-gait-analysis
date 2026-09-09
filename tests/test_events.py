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
