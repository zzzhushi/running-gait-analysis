"""End-to-end validation against a real 102.8 spm side-view clip.

This fixture protects low-cadence event detection, including strike count and same-foot
stride timing. Its ground truth is measured from raw pixels independently of the pose model.
See the accompanying ground-truth JSON for measurement provenance and known limitations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
POSE = DATA / "female_overstride.pose.json"
TRUTH = DATA / "female_overstride.groundtruth.json"

CADENCE_TOLERANCE_PCT = 2.0

pytestmark = pytest.mark.skipif(
    not POSE.exists() or not TRUTH.exists(),
    reason=f"real-clip fixture not present ({POSE.name}); see tests/data/README.md",
)

# Contact boundaries use an uncalibrated ankle-motion proxy. Strict xfail makes an eventual
# correction require explicit acceptance rather than silently disappearing from the suite.
uncalibrated_stance = pytest.mark.xfail(
    strict=True,
    reason="ankle-amplitude contact proxy is uncalibrated; see the ground-truth record",
)


@pytest.fixture(scope="module")
def truth() -> dict:
    return json.loads(TRUTH.read_text())


@pytest.fixture(scope="module")
def seq(truth):
    from gaitlab.core.schema import PoseSequence

    s = PoseSequence.from_pose_dict(json.loads(POSE.read_text())).validate()
    assert s.view == truth["view"], "fixture view drifted from the ground-truth record"
    return s


@pytest.fixture(scope="module")
def events(seq):
    from gaitlab.core.events import detect_events

    return detect_events(seq)


@pytest.fixture(scope="module")
def result(seq) -> dict:
    from gaitlab.analyze import analyze

    return analyze(seq, label="female_overstride").to_dict()


def _metric(result: dict, key: str):
    for m in result["metrics"]:
        if m["key"] == key:
            return m["value"]
    raise AssertionError(f"metric {key!r} is not in the report")


# --------------------------------------------------------------------------- fixture

def test_pose_fixture_is_intact(seq):
    assert seq.n == 1160, f"expected 1160 frames, got {seq.n}"
    assert seq.timestamps is not None, "real per-frame timestamps were dropped"
    assert seq.duration == pytest.approx(9.675, abs=0.01)


def test_engine_reads_the_real_frame_rate(seq):
    assert seq.effective_fps == pytest.approx(119.9, abs=0.5)


# --------------------------------------------------------------------------- cadence

def test_cadence_matches_ground_truth(result, truth):
    expected = truth["cadence_spm"]["value"]
    actual = result["summary"]["cadence"]
    err_pct = abs(actual - expected) / expected * 100
    assert err_pct <= CADENCE_TOLERANCE_PCT, (
        f"cadence {actual:.2f} spm is {err_pct:.1f}% from the measured {expected} spm "
        f"(tolerance {CADENCE_TOLERANCE_PCT}%)"
    )


def test_strike_count_is_consistent_with_cadence(events, seq, truth):
    """Event count catches duplicated strikes that interval averaging can hide."""
    expected = truth["cadence_spm"]["value"] / 60.0 * seq.duration
    actual = len(events.strikes["l"]) + len(events.strikes["r"])
    err_pct = abs(actual - expected) / expected * 100
    assert err_pct <= 10.0, (
        f"detected {actual} strikes over {seq.duration:.2f}s, but the measured cadence "
        f"implies ~{expected:.0f} ({err_pct:.0f}% off). More than ~2x means a spurious "
        f"swing-phase peak is being counted as a contact."
    )


def test_same_foot_events_are_a_stride_apart(events, seq, truth):
    stride_s = 120.0 / truth["cadence_spm"]["value"]
    for side in ("l", "r"):
        got = events.stride_time.get(side)
        assert got is not None, f"no stride time for side {side!r}"
        err_pct = abs(got - stride_s) / stride_s * 100
        assert err_pct <= 10.0, (
            f"{side}: stride time {got:.3f}s vs measured {stride_s:.3f}s ({err_pct:.0f}% "
            f"off). A value near half the truth means consecutive same-foot peaks are a "
            f"STEP apart, i.e. a spurious mid-swing peak is being detected."
        )


# ------------------------------------------------------------ stance, from 120 fps

@uncalibrated_stance
def test_contact_time_is_physiological(result, truth):
    """Contact time stays within the clip's pixel-measured physiological band.

    This remains a strict xfail because a fixed ankle-amplitude threshold is not calibrated
    across runners. The ground-truth record contains the supporting sweeps and alternatives.
    """
    lo, hi = truth["physiological_bands"]["contact_time_ms"]
    gct = _metric(result, "contact_time")
    assert lo <= gct <= hi, f"ground contact time {gct:.0f} ms is outside {lo}-{hi} ms"


@uncalibrated_stance
def test_duty_factor_is_physiological(result, truth):
    lo, hi = truth["physiological_bands"]["duty_factor_pct"]
    duty = _metric(result, "duty_factor")
    assert lo <= duty <= hi, f"duty factor {duty:.1f}% is outside {lo}-{hi}%"


def test_duty_factor_and_flight_time_do_not_contradict_each_other(result):
    """Double-support duty factor and positive flight time cannot coexist."""
    duty = _metric(result, "duty_factor")
    flight = _metric(result, "flight_time")
    assert not (duty > 50.0 and flight > 0.0), (
        f"duty factor {duty:.1f}% says both feet are on the ground at once, but flight "
        f"time is {flight:.0f} ms. These cannot both be true."
    )


# --------------------------------------------------------------------------- quality

def test_no_spurious_ground_tilt_warning(result):
    """Incorrect strike frames must not create a tilt warning on a level clip."""
    tilt = [f for f in (result.get("quality") or [])
            if "tilt" in f.get("message", "").lower()]
    assert not tilt, f"spurious ground-tilt warning on a clip measured level: {tilt}"
