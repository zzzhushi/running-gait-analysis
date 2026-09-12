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


# --- event-confidence grade ---------------------------------------------------
#
# The grade is only worth reporting if it can say something other than "high". Every
# synthetic fixture and the full real clip grade "high", so none of them demonstrate
# that. These derive degraded clips from the same committed pose — no extra footage —
# and pin each tier to the condition that produces it.


def _degraded(frames=None, drop_side=None):
    """The real pose, optionally truncated and/or with one foot untracked."""
    pose = json.loads(POSE.read_text())
    if frames is not None:
        pose["frames"] = pose["frames"][:frames]
        pose["timestamps"] = pose["timestamps"][:frames]
    if drop_side:
        from gaitlab.core.schema import KEYPOINTS

        idx = {KEYPOINTS.index(f"{drop_side}_{p}") for p in ("ankle", "heel", "big_toe")}
        pose["frames"] = [
            [(0.0, 0.0, 0.0) if i in idx else pt for i, pt in enumerate(frame)]
            for frame in pose["frames"]
        ]
    from gaitlab.core.events import detect_events
    from gaitlab.core.schema import PoseSequence

    return detect_events(PoseSequence.from_pose_dict(pose))


def test_full_clip_earns_high_confidence(events):
    ev, _ = events
    assert ev.confidence == "high"
    assert ev.warnings == []
    assert ev.alternation_ratio == pytest.approx(1.0)


def test_a_short_clip_is_downgraded_to_moderate():
    """Two seconds is enough to measure but not enough to be confident in the spread."""
    ev = _degraded(frames=60)
    assert ev.confidence == "moderate"
    assert len(ev.stance["l"]) + len(ev.stance["r"]) < 8


def test_too_few_stances_is_low_and_says_so():
    ev = _degraded(frames=30)
    assert ev.confidence == "low"
    assert "too_few_complete_stances" in ev.warnings


def test_an_untracked_foot_is_low_and_names_the_alternation_failure():
    """Losing one foot leaves contacts that never alternate — the single most
    diagnostic sign that event detection has failed, and the case that used to be
    reported as a perfect 1.0 alternation ratio."""
    ev = _degraded(drop_side="l")
    assert ev.confidence == "low"
    assert ev.alternation_ratio == pytest.approx(0.0)
    assert "inconsistent_left_right_alternation" in ev.warnings


def test_the_grade_spans_every_tier_across_these_inputs():
    """Guards the grade against collapsing to a constant, which is how it shipped:
    inert, because every available clip produced the same answer."""
    grades = {
        _degraded().confidence,
        _degraded(frames=60).confidence,
        _degraded(frames=30).confidence,
    }
    assert grades == {"high", "moderate", "low"}


# --- measurement repeatability (MDC) ------------------------------------------
#
# asymmetry.py exposes `asymmetry_mdc` but every metric leaves it None, so a left/right
# difference is reported with no way to tell it from noise. This measures the noise floor
# for the one clip where that is possible.
#
# WHAT THIS IS: the standard error of the *aggregate* under resampling of the strides the
# clip contains, converted to MDC95 = 1.96 * sqrt(2) * SE ~= 2.77 * SE. Resampling the
# aggregate rather than taking the raw stride-to-stride SD matters: stride time genuinely
# varies between strides, and that biological variability averages out in the reported
# number exactly as it does here, leaving sampling noise.
#
# WHAT THIS IS NOT: a test-retest MDC. It cannot see camera repositioning, lighting,
# pose-model run-to-run variation, or day-to-day physiology, because it has one recording.
# It is therefore a LOWER BOUND. A difference below it is definitely not interpretable;
# a difference above it is not yet proven to be.
#
# Populating MetricDef.asymmetry_mdc needs the real protocol: ~10 clips of one runner
# under conditions you would call identical, SD of the aggregate across them, x2.77.

MDC_BOOTSTRAP_SAMPLES = 2000
MDC_SEED = 7


def _aggregate_se_ms(series, seed=MDC_SEED):
    """Standard error (ms) of the reported aggregate, by resampling strides."""
    import random
    import statistics

    from gaitlab.core.events import _robust_period

    rng = random.Random(seed)
    aggregates = [
        _robust_period([rng.choice(series) for _ in series]) * 1000.0
        for _ in range(MDC_BOOTSTRAP_SAMPLES)
    ]
    return statistics.stdev(aggregates)


def _mdc95_ms(series):
    return 2.77 * _aggregate_se_ms(series)


def test_contact_time_noise_floor_is_small_relative_to_the_value(events):
    """A ~15 ms floor on a ~223 ms contact time is ~7%.

    If event detection gets noisier — a jitterier anchor, contacts dropped and
    re-found — this grows, and the report starts presenting differences it cannot
    actually resolve. That is the regression this guards.
    """
    ev, _ = events
    contacts = [v for side in ("l", "r") for v in ev.contact_times[side]]
    assert len(contacts) >= 20, "too few stances to estimate a noise floor"

    mdc = _mdc95_ms(contacts)
    mean_ms = sum(contacts) / len(contacts) * 1000.0
    assert 5.0 <= mdc <= 30.0, f"contact-time MDC95 {mdc:.1f} ms is outside the expected range"
    assert mdc / mean_ms <= 0.15, (
        f"contact-time noise floor is {mdc / mean_ms * 100:.0f}% of the value "
        f"({mdc:.1f} ms of {mean_ms:.0f} ms) — differences below that are unresolvable"
    )


def test_left_right_contact_difference_is_reported_against_its_noise_floor(events):
    """On this clip the L/R difference clears the floor, so it is not pure noise.

    That does not make it a real gait asymmetry: a side view occludes the far leg, so
    the far foot's contacts are tracked worse, and this is exactly the shape that
    artifact takes. It is recorded here so the number has a scale attached rather than
    being presented bare, and so a future change that inflates it gets noticed.
    """
    ev, _ = events
    left, right = ev.contact_times["l"], ev.contact_times["r"]
    diff_ms = abs(ev.contact_time["l"] - ev.contact_time["r"]) * 1000.0
    # Two independent estimates, so the difference's floor combines them in quadrature.
    floor = 2.77 * (_aggregate_se_ms(left) ** 2 + _aggregate_se_ms(right) ** 2) ** 0.5

    assert diff_ms > floor, (
        f"L/R contact difference {diff_ms:.1f} ms no longer clears its {floor:.1f} ms "
        f"noise floor; the fixture or the detector changed"
    )
    assert diff_ms < 80.0, (
        f"L/R contact difference {diff_ms:.1f} ms is implausibly large for one runner; "
        f"the far leg is probably being lost"
    )
