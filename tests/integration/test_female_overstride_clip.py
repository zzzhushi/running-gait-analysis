"""End-to-end regression test against a real 102.8 spm clip that the engine gets wrong.

This is the companion to test_male_side_clip.py, and the difference between them is the
point. `male_side.mp4` runs at 168.9 spm, where gait-event detection happens to work, so it
can only prove the engine has not regressed. This clip runs at 102.8 spm, where detection
does not work — so it proves the engine is wrong, and it is the exit criterion for fixing
it. A suite whose only real fixture is one the code already passes cannot do that.

Ground truth came from raw pixels: four independent signals (head-top row, silhouette
centroid, leg-band motion energy, foot-band spread), each read by both a fine-grid DFT and
a 4-harmonic autocorrelation ladder, plus two cross-checks of different physics — the
spacing of flight phases found from the shoe's bright midsole, and a direct count of head
apexes. All eight estimates land in 102.28-103.91 spm. No pose model and no part of this
engine was involved. See tests/data/female_overstride.groundtruth.json for the full method,
including why `scripts/measure_cadence_groundtruth.py` cannot measure this clip.

WHAT IS BROKEN, as of commit c4f6389:

    cadence        126.87 spm     truth 102.8      +23.4%
    strikes        16 L + 18 R    truth ~16.6      2.05x too many
    contact time   332 / 215 ms   truth 505 ms     low, and asymmetric for no reason
    duty factor    57.3%          truth 44%        >50% means walking
    flight time    199.5 ms       truth 75 ms      contradicts a 57.3% duty factor

One root cause. `events.py` spaces ankle-y peaks with `min_dist = max(3, int(fps * 0.35))`,
an absolute-time guard against a defect that scales with the stride: the spurious
swing-phase peak sits at a roughly fixed FRACTION of the stride (~0.4), so at 168.9 spm it
falls 0.28 s out and the guard rejects it, while at 102.8 spm it falls 0.47 s out and
survives. `_robust_period` then converts the doubled event list into a plausible-looking
wrong answer rather than an obviously broken one — its median-anchored 0.6x-1.6x trim
window comes out as [0.215, 0.573] s, and the true step period of 0.5837 s falls just
outside it, so the one correct gap in the list is discarded.

Note the frame rate is NOT the cause. This clip carries real 120 fps container timestamps
and the engine reads them correctly (`effective_fps` = 119.896). The bug is frame-rate
independent.

These tests are `xfail(strict=True)`: CI stays green while the bug is open, and the moment
the engine gets cadence right they XPASS, which fails the run until the marker is removed.
That is deliberate — the marker is the todo list, and it cannot be forgotten.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
POSE = DATA / "female_overstride.pose.json"
TRUTH = DATA / "female_overstride.groundtruth.json"

# Cadence is the headline number in the report, and it is derived from gaps between
# detected events, so it is the tightest available probe of whether those events are real.
CADENCE_TOLERANCE_PCT = 2.0

pytestmark = pytest.mark.skipif(
    not POSE.exists() or not TRUTH.exists(),
    reason=f"real-clip fixture not present ({POSE.name}); see tests/data/README.md",
)

# Remove this marker when gait-event detection is fixed. Do not loosen the tolerances
# instead: the measured truth is good to +/-0.6 spm and the engine is 23% away.
broken = pytest.mark.xfail(
    strict=True,
    reason="gait-event detection doubles at low cadence; see this module's docstring",
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
    """Fail loudly if the fixture was truncated or re-extracted with a different model."""
    assert seq.n == 1160, f"expected 1160 frames, got {seq.n}"
    assert seq.timestamps is not None, "real per-frame timestamps were dropped"
    assert seq.duration == pytest.approx(9.675, abs=0.01)


def test_engine_reads_the_real_frame_rate(seq):
    """The 120 fps timebase reaches the engine intact.

    This is asserted so that no cadence failure below can be blamed on frame rate. The
    clip is 120 fps, the container timestamps are real, and the engine sees them.
    """
    assert seq.effective_fps == pytest.approx(119.9, abs=0.5)


# --------------------------------------------------------------------------- cadence

@broken
def test_cadence_matches_ground_truth(result, truth):
    """THE EXIT CRITERION.

    102.8 +/- 0.6 spm, measured from pixels by eight independent estimates.
    """
    expected = truth["cadence_spm"]["value"]
    actual = result["summary"]["cadence"]
    err_pct = abs(actual - expected) / expected * 100
    assert err_pct <= CADENCE_TOLERANCE_PCT, (
        f"cadence {actual:.2f} spm is {err_pct:.1f}% from the measured {expected} spm "
        f"(tolerance {CADENCE_TOLERANCE_PCT}%)"
    )


@broken
def test_strike_count_is_consistent_with_cadence(events, seq, truth):
    """Count events independently of the gaps between them.

    Cadence is computed from inter-event gaps, so a detector that invents a whole extra
    event per stride can still report a plausible median gap. Counting catches what
    averaging hides — and here the count is 2.05x the truth while cadence is only 23% off,
    which is exactly that effect.
    """
    expected = truth["cadence_spm"]["value"] / 60.0 * seq.duration
    actual = len(events.strikes["l"]) + len(events.strikes["r"])
    err_pct = abs(actual - expected) / expected * 100
    assert err_pct <= 10.0, (
        f"detected {actual} strikes over {seq.duration:.2f}s, but the measured cadence "
        f"implies ~{expected:.0f} ({err_pct:.0f}% off). More than ~2x means a spurious "
        f"swing-phase peak is being counted as a contact."
    )


@broken
def test_same_foot_events_are_a_stride_apart(events, seq, truth):
    """Consecutive events on ONE foot are a stride apart, never a step.

    This is the most direct statement of the bug. The true stride here is 1.167 s; main
    produces ~0.58 s for both feet, which is the step period — the signature of one
    phantom event interleaved between each pair of real ones.
    """
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

@broken
def test_contact_time_is_physiological(result, truth):
    """Unlike male_side's, this band is measured from the clip, not taken from literature.

    At 120 fps a stance is ~60 frames, so contact time is resolved rather than argued over.
    """
    lo, hi = truth["physiological_bands"]["contact_time_ms"]
    gct = _metric(result, "contact_time")
    assert lo <= gct <= hi, f"ground contact time {gct:.0f} ms is outside {lo}-{hi} ms"


@broken
def test_duty_factor_is_physiological(result, truth):
    lo, hi = truth["physiological_bands"]["duty_factor_pct"]
    duty = _metric(result, "duty_factor")
    assert lo <= duty <= hi, f"duty factor {duty:.1f}% is outside {lo}-{hi}%"


@broken
def test_duty_factor_and_flight_time_do_not_contradict_each_other(result):
    """A duty factor over 50% means both feet are down at once — so there is no flight.

    Main reports 57.3% duty AND 199.5 ms of flight in the same report. Neither number needs
    ground truth to be shown wrong; they refute each other. Nothing in the engine currently
    notices, because quality.assess() is never given the computed metrics.
    """
    duty = _metric(result, "duty_factor")
    flight = _metric(result, "flight_time")
    assert not (duty > 50.0 and flight > 0.0), (
        f"duty factor {duty:.1f}% says both feet are on the ground at once, but flight "
        f"time is {flight:.0f} ms. These cannot both be true."
    )


# --------------------------------------------------------------------------- quality

@broken
def test_no_spurious_ground_tilt_warning(result):
    """The tilt check fits a line through ankle positions AT DETECTED STRIKES.

    Phantom mid-swing strikes tilt that line however level the camera is. Five scene edges
    traced independently on this clip are all within 2.5 deg and the belt line from planted
    soles is 1.5 deg, both under the check's ~3.4 deg threshold — so this warning is a
    symptom of the strike bug, not a capture fault. It should disappear when strikes are
    fixed; if it does not, the check has a second, independent problem.
    """
    tilt = [f for f in (result.get("quality") or [])
            if "tilt" in f.get("message", "").lower()]
    assert not tilt, f"spurious ground-tilt warning on a clip measured level: {tilt}"
