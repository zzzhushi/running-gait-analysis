"""End-to-end regression test against a real running clip with a known cadence.

Every other test in this suite feeds the engine synthetic pose, where the answer is known
because the generator put it there. That catches maths errors but not modelling errors —
it cannot tell you that "foot strike" is detected half a step late, because the synthetic
generator and the detector share the same assumption.

This test uses a real clip whose cadence was measured from raw pixels, independently of
any pose model or of this engine (see tests/data/male_side.groundtruth.json, regenerate
with scripts/measure_cadence_groundtruth.py). It is the only place where the engine is
checked against ground truth it did not produce.

The two physiological-band assertions are not cosmetic: ground contact time and duty
factor are the observable consequences of where gait events are anchored. Anchoring a
"strike" at the ankle's lowest point (midstance) rather than at initial contact roughly
halves both, so these bands are what stops that class of regression coming back.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
POSE = DATA / "male_side.pose.json"
TRUTH = DATA / "male_side.groundtruth.json"

# Guards the class of regression this project has actually shipped: cadence scaling by a
# dropped-frame factor (a real 165 spm reported as 200). Deliberately loose so it does not
# fail on the known median-gap quantization; `test_cadence_matches_ground_truth` is the
# tight one.
REGRESSION_TOLERANCE_PCT = 5.0
# What the engine should manage once cadence is not quantized onto the integer-frame grid.
ACCURATE_TOLERANCE_PCT = 1.5

pytestmark = pytest.mark.skipif(
    not POSE.exists() or not TRUTH.exists(),
    reason=f"real-clip fixture not present ({POSE.name}); see tests/data/README.md",
)


@pytest.fixture(scope="module")
def truth() -> dict:
    return json.loads(TRUTH.read_text())


@pytest.fixture(scope="module")
def result(truth) -> dict:
    """The full analysis result for the real clip."""
    from gaitlab.analyze import analyze
    from gaitlab.core.schema import PoseSequence

    pose = json.loads(POSE.read_text())
    seq = PoseSequence.from_pose_dict(pose).validate()
    assert seq.view == truth["view"], "fixture view drifted from the ground-truth record"
    return analyze(seq, label="male_side").to_dict()


@pytest.fixture(scope="module")
def events(truth):
    from gaitlab.core.events import detect_events
    from gaitlab.core.schema import PoseSequence

    seq = PoseSequence.from_pose_dict(json.loads(POSE.read_text()))
    return detect_events(seq), seq


def _metric(result: dict, key: str):
    for m in result["metrics"]:
        if m["key"] == key:
            return m["value"]
    raise AssertionError(f"metric {key!r} is not in the report")


def test_pose_fixture_is_intact(events):
    """Fail loudly if the fixture was truncated or re-extracted with a different model."""
    _, seq = events
    assert seq.n == 360, f"expected 360 frames, got {seq.n}"
    assert seq.fps == pytest.approx(30.0, abs=0.01)
    assert seq.timestamps is not None, "real per-frame timestamps were dropped"


def test_cadence_within_regression_band(result, truth):
    """The engine's cadence must not drift far from the measured truth.

    This is the assertion that would have caught the dropped-frame fps bug, where a real
    165 spm was reported as 200.
    """
    expected = truth["cadence_spm"]["value"]
    actual = result["summary"]["cadence"]
    err_pct = abs(actual - expected) / expected * 100
    assert err_pct <= REGRESSION_TOLERANCE_PCT, (
        f"cadence {actual:.2f} spm is {err_pct:.1f}% from the measured "
        f"{expected} spm (tolerance {REGRESSION_TOLERANCE_PCT}%)"
    )


def test_cadence_matches_ground_truth(result, truth):
    expected = truth["cadence_spm"]["value"]
    actual = result["summary"]["cadence"]
    err_pct = abs(actual - expected) / expected * 100
    assert err_pct <= ACCURATE_TOLERANCE_PCT, (
        f"cadence {actual:.2f} spm is {err_pct:.1f}% from the measured {expected} spm"
    )


def test_contact_time_is_physiological(result, truth):
    """Ground contact time roughly halves if events are anchored at midstance."""
    lo, hi = truth["physiological_bands"]["contact_time_ms"]
    gct = _metric(result, "contact_time")
    assert lo <= gct <= hi, (
        f"ground contact time {gct:.0f} ms is outside {lo}-{hi} ms. A value near half the "
        f"lower bound usually means gait events are anchored at midstance rather than at "
        f"initial contact."
    )


def test_duty_factor_is_physiological(result, truth):
    lo, hi = truth["physiological_bands"]["duty_factor_pct"]
    duty = _metric(result, "duty_factor")
    assert lo <= duty <= hi, (
        f"duty factor {duty:.1f}% is outside {lo}-{hi}%. Same cause as contact time: "
        f"stance measured from midstance instead of initial contact."
    )


def test_strike_count_is_consistent_with_cadence(events, truth):
    """Cross-check the event detector against the measured cadence.

    Cadence is derived from the gaps between strikes, so a detector that drops or invents
    whole contacts can still report a plausible median gap. Counting them independently
    catches that.
    """
    ev, seq = events
    expected_steps = truth["cadence_spm"]["value"] / 60.0 * seq.duration
    actual_steps = len(ev.strikes["l"]) + len(ev.strikes["r"])
    err_pct = abs(actual_steps - expected_steps) / expected_steps * 100
    assert err_pct <= 8.0, (
        f"detected {actual_steps} strikes over {seq.duration:.1f}s, but the measured "
        f"cadence implies ~{expected_steps:.0f} ({err_pct:.1f}% off)"
    )


def test_both_feet_are_tracked(events):
    """A side view occludes the far leg; if it degrades badly, per-side metrics are noise."""
    ev, _ = events
    n_l, n_r = len(ev.strikes["l"]), len(ev.strikes["r"])
    assert min(n_l, n_r) > 0, "one foot produced no contacts at all"
    imbalance = abs(n_l - n_r) / max(n_l, n_r) * 100
    assert imbalance <= 15.0, (
        f"left/right strike counts differ by {imbalance:.0f}% (L={n_l} R={n_r}); "
        f"the far leg is probably being lost"
    )
