"""Capture-quality checks (gaitlab/metrics/quality.py)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List

import pytest

from gaitlab.core.events import detect_events
from gaitlab.core.schema import KEYPOINTS, KP_INDEX, PoseSequence
from gaitlab.core.tracking import leg_trust
from gaitlab.metrics import quality


def _checks(seq, level=None):
    ev = detect_events(seq)
    checks = quality.assess(seq, ev)
    return [c["message"] for c in checks if level is None or c["level"] == level]


# ------------------------------------------------------------------ fps wording


def test_no_slow_mo_hint_for_a_clip_that_reports_119_9_fps(synth):
    """A clip captured at 120 fps commonly reports 119.88-119.9 (NTSC-style rates);
    it should not be told to shoot the frame rate it already shot."""
    seq = synth("side-left", fps=119.9, duration=4, cadence=170, seed=1)
    assert not any("fps" in m for m in _checks(seq, "info"))


def test_slow_mo_hint_still_fires_below_120(synth):
    seq = synth("side-left", fps=60, duration=4, cadence=170, seed=1)
    assert any("fps" in m for m in _checks(seq, "info"))


# ------------------------------------------------------------------ tracking dropout


def test_no_dropout_warning_on_a_clean_clip(synth):
    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=1)
    assert not any("tracking" in m.lower() for m in _checks(seq, "warn"))


def _drop_legs(seq, lo, hi):
    frames = list(seq.frames)
    for i in range(lo, hi):
        flat = list(frames[i])
        for name in ("l_ankle", "l_knee", "l_hip", "r_ankle", "r_knee", "r_hip"):
            x, y, _ = flat[KP_INDEX[name]]
            flat[KP_INDEX[name]] = (x, y, 0.05)
        frames[i] = flat
    return replace(seq, frames=frames)


def test_dropout_warning_when_both_legs_lose_tracking(synth):
    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=1)
    dropped = _drop_legs(seq, seq.n // 2, seq.n // 2 + 45)  # 0.75s at 60fps
    assert any("tracking" in m.lower() for m in _checks(dropped, "warn"))


def test_dropout_warning_carries_its_frame_span_for_the_overlay(synth):
    """The timeline ribbon (web/js/overlay.js) needs a frame range to hatch out, not
    just a human-readable message — the two must describe the same span."""
    seq = synth("side-left", fps=60, duration=6, cadence=170, seed=1)
    lo, hi = seq.n // 2, seq.n // 2 + 45
    dropped = _drop_legs(seq, lo, hi)
    ev = detect_events(dropped)
    checks = quality.assess(dropped, ev)
    dropout = next(c for c in checks if "tracking" in c["message"].lower())
    assert dropout.get("frames") is not None
    f0, f1 = dropout["frames"]
    assert lo - 2 <= f0 <= lo + 2
    assert hi - 2 <= f1 <= hi + 2


# ------------------------------------------------------------------ ground-slope trust


@dataclass
class _FakeEvents:
    strikes: Dict[str, List[int]] = field(default_factory=dict)


def _flat_pose(n=20, width=1000, height=800):
    frames = []
    for i in range(n):
        fr = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        x = (i / (n - 1)) * width
        for name, y in (("l_hip", 400.0), ("l_knee", 550.0), ("l_ankle", 700.0)):
            fr[KP_INDEX[name]] = (x, y, 1.0)
        frames.append(fr)
    return PoseSequence(fps=60, width=width, height=height, view="side-left",
                        frames=frames, source="test")


def test_ground_slope_ignores_an_implausibly_tracked_strike():
    from gaitlab.metrics.quality import _ground_slope

    seq = _flat_pose()
    events = _FakeEvents(strikes={"l": [2, 6, 10, 14, 18], "r": []})
    frames = list(seq.frames)
    # Displace the strike furthest from the sample's mean x, so it has leverage on the fit.
    x, y, c = frames[18][KP_INDEX["l_ankle"]]
    flat = list(frames[18])
    flat[KP_INDEX["l_ankle"]] = (x, y - 500.0, c)  # mistracked, but still "confident"
    frames[18] = flat
    tilted = replace(seq, frames=frames)

    naive = _ground_slope(tilted, events)
    assert naive is not None and abs(naive) > 0.06  # the outlier alone reads as tilted

    trust = {"l": leg_trust(tilted, "l"), "r": leg_trust(tilted, "r")}
    filtered = _ground_slope(tilted, events, trust=trust)
    assert filtered is None or abs(filtered) <= 0.06
